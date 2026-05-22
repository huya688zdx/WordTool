"""AI-assisted heading level detection and correction."""

from __future__ import annotations

import json
import re
import time

from app.ai import get_ai_logger, get_conv_logger

_log = get_ai_logger()
_conv_log = get_conv_logger()

HEADING_DETECT_PROMPT = """You are a document structure proofreader. Word COM has pre-assigned heading levels, but its detection is seriously broken. Your job: analyze the document's REAL logical structure, then fix heading levels.

## Step 1 — Analyze Document Structure FIRST
Read ALL paragraphs. Understand how many levels this document ACTUALLY has:
- If it's chapters → sections → that's H1 + H2 (2 levels)
- If it's chapters → sections → sub-sections → that's H1 + H2 + H3 (3 levels)
- MOST Chinese technical documents only have 2 levels (H1 + H2)

## Step 2 — Assign Levels Based on Content
**CRITICAL: Only use levels this document actually needs. Do NOT invent H3/H4/H5 if the document only has H1+H2 structure.**

| Document Role | Assign |
|---|---|
| Chapter / major section: "第X章", numbered "1.", "一、", or top-level topic | H1 |
| Sub-section within a chapter: "1.1", "（一）", or clearly subordinate to H1 | H2 |
| Deep sub-section: "1.1.1" — only if document truly has 3-level nesting | H3 |
| Body paragraph (long text) | 0 |

## Step 3 — Fix Word COM Bugs
- H6~H10 → ALWAYS wrong, fix to H1 or H2 based on content and heading position
- Lv=0 (·) section titles → COM missed them, assign H1 or H2
- Body text marked as any heading → demote to 0

## Position Cues (P=page, Y=vertical pos, H=text height)
- Page top (small Y) + new topic → likely H1
- Larger H (bigger font) → more likely a heading

## Rules
1. Analyze the document's REAL hierarchy first — don't blindly apply a fixed mapping
2. H6~H10 always wrong → H1 or H2 (not H3/H4/H5!)
3. Only use H3 if document has "1.1.1" style deep nesting
4. NEVER use H4 or deeper unless absolutely certain
5. Body text wrongly marked as heading → 0
6. ERR ON CORRECTING. Return empty ONLY if every level is perfect.

## Output
Return ONLY JSON:
{"corrections": [{"index": 5, "heading_level": 1, "reason": "H10→H1: 第1章 概述，章标题"}]}

heading_level meanings:
- 0: body text
- 1: chapter / major section
- 2: sub-section
- 3: deep sub-section (rare, only if doc has 3-level nesting)

DO NOT return {"corrections": []} casually. Only if every single paragraph's level is perfect."""


def detect_headings(
    api_key: str, base_url: str, model: str,
    paragraphs: list[dict],
    positions: list[dict] | None = None,
) -> list[dict]:
    """Send paragraph list to AI for heading level analysis.

    Args:
        paragraphs: list of dicts with index, heading_level, text
        positions: optional list of dicts with para_index, page, x0, y0, x1, y1
    """
    from openai import OpenAI

    # Build position lookup
    pos_map = {}
    if positions:
        for wp in positions:
            pos_map[wp.get("para_index", 0)] = wp

    # Build clear representation: numbered index, level marker, FULL text, position
    lines = []
    for p in paragraphs:
        idx = p["index"]
        level = p.get("heading_level") or 0
        text = (p.get("text") or "").strip()
        marker = f"H{level}" if level > 0 else " · "

        wp = pos_map.get(idx)
        if wp:
            page = wp.get("page", "?")
            y0 = wp.get("y0", 0)
            y1 = wp.get("y1", 0)
            height = y1 - y0
            pos_str = f"P{page} Y{y0:.0f} H{height:.0f}"
        else:
            pos_str = "P? -"

        lines.append(f"[{idx:04d}] {marker} {pos_str} | {text}")

    para_text = "\n".join(lines)

    pos_hint = ""
    if positions:
        pos_hint = """\n## Position Hints
- P=Page number, Y=vertical position (top of page = small Y), H=text block height
- Paragraphs at page top (small Y) starting a new topic → likely H1
- Larger H (height) usually means larger font → more likely a heading
- Independent / self-contained modules → treat as H1 even without number prefix
"""

    user_prompt = f"""Review the COMPLETE document below. Every paragraph is listed with its full text, current Word COM heading level, and page position.

Format: [index] marker P? Y? H? | full_text
  H1/H2/... = existing heading level from Word COM (may be WRONG!)
  · = normal text (Lv=0, but might actually be a heading)
{pos_hint}

=== FULL DOCUMENT CONTENT ===

{para_text}

=== END OF DOCUMENT ===

Read through all {len(paragraphs)} paragraphs. Understand the document's logical structure, then:
1. Find · (Lv=0) paragraphs that are actually headings → assign correct heading_level
2. Find existing headings with WRONG levels (e.g., H10 should be H1, H3 should be H2) → fix them
3. Find body text incorrectly marked as heading → set heading_level to 0

Return ONLY JSON corrections. Include ALL paragraphs whose heading_level needs to change."""

    from app.ai import make_http_client
    client = OpenAI(api_key=api_key, base_url=base_url, http_client=make_http_client())
    request_id = f"heading-{int(time.time() * 1000)}"
    _log.info("[REQ %s] model=%s base_url=%s paragraphs=%d", request_id, model, base_url, len(paragraphs))
    _log.debug("[REQ %s] system_prompt=%s", request_id, HEADING_DETECT_PROMPT[:200])
    _log.debug("[REQ %s] user_prompt=%s", request_id, user_prompt[:500])

    # Full conversation log
    _conv_log.info("=== REQ %s ===", request_id)
    _conv_log.info("model=%s base_url=%s paragraphs=%d", model, base_url, len(paragraphs))
    _conv_log.info("--- system ---\n%s", HEADING_DETECT_PROMPT)
    _conv_log.info("--- user ---\n%s", user_prompt)

    t0 = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": HEADING_DETECT_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=16384,
        )
        elapsed = time.time() - t0
        content = response.choices[0].message.content or ""
        usage = response.usage
        _log.info("[RES %s] elapsed=%.1fs tokens_in=%d tokens_out=%d",
                   request_id, elapsed,
                   usage.prompt_tokens if usage else 0,
                   usage.completion_tokens if usage else 0)
        _log.debug("[RES %s] content=%s", request_id, content[:500])

        finish_reason = response.choices[0].finish_reason or ""
        _conv_log.info("=== RES %s elapsed=%.1fs tokens_in=%d tokens_out=%d finish=%s ===",
                       request_id, elapsed,
                       usage.prompt_tokens if usage else 0,
                       usage.completion_tokens if usage else 0,
                       finish_reason)
        _conv_log.info("%s", content)

        if finish_reason == "length":
            _log.warning("[RES %s] output TRUNCATED by token limit!", request_id)

        # Parse JSON
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                json_str = content[brace_start:brace_end + 1]
            else:
                _log.warning("[RES %s] no JSON found in response, content=%s", request_id, content[:200])
                return []

        if not json_str:
            _log.warning("[RES %s] empty JSON string", request_id)
            return []

        corrections = _parse_with_repair(json_str, request_id)
        if corrections is None:
            return []

        _log.info("[RES %s] %d heading corrections", request_id, len(corrections))
        for c in corrections:
            _log.debug("[RES %s]   index=%d level=%d reason=%s",
                        request_id, c.get("index"), c.get("heading_level"), c.get("reason", ""))
        return corrections

    except Exception as e:
        _log.error("[ERR %s] heading detect failed: %s", request_id, e)
        return []


def _parse_with_repair(json_str: str, request_id: str) -> list[dict] | None:
    """Parse JSON, with progressive repair for truncated output. Returns None on total failure."""
    try:
        data = json.loads(json_str)
        return data.get("corrections", [])
    except json.JSONDecodeError as e:
        _log.warning("[RES %s] JSON parse failed (will try repair): %s", request_id, str(e))

    in_string = json_str.count('"') % 2 == 1
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")

    attempts = []
    if in_string:
        attempts.extend([json_str + '"}', json_str + ']"}', json_str + '"}]}'])
    suffix = "]" * open_brackets + "}" * open_braces
    if suffix:
        attempts.append(json_str + suffix)
    last_comma = json_str.rfind(",")
    if last_comma > 0 and open_braces > 0:
        attempts.append(json_str[:last_comma] + "}]}")

    for attempt in attempts:
        try:
            data = json.loads(attempt)
            corrections = data.get("corrections", [])
            if corrections:
                _log.info("[RES %s] JSON repaired: salvaged %d corrections", request_id, len(corrections))
            return corrections
        except json.JSONDecodeError:
            continue

    _log.warning("[RES %s] All JSON repair attempts failed. Raw: %s", request_id, json_str[:500])
    return None
