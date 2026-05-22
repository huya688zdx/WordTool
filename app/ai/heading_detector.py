"""AI-assisted heading level detection and correction."""

from __future__ import annotations

import json
import re
import time

from app.ai import get_ai_logger, get_conv_logger

_log = get_ai_logger()
_conv_log = get_conv_logger()

HEADING_DETECT_PROMPT = """You are a strict document proofreader. Word COM has pre-assigned heading levels to every paragraph, but its levels are FREQUENTLY WRONG. Your job is to find and fix EVERY error in the complete document.

## CRITICAL: Word COM Systematic Errors
Word COM's heading detection has KNOWN bugs:
- Chapter titles (第X章, 概述, 引言) often get H6~H10 instead of H1
- Numbered sections (2.1, 3.2.1) often get wrong levels or Lv=0
- Body text sometimes gets falsely promoted to a heading level
- Chinese numbered headings (一、, （二）) are frequently missed (Lv=0)

## Exact Level Rules — Apply These Strictly
| Text Pattern | Correct Level |
|---|---|
| 第X章, 第X部分, 概述, 引言, 背景, 总结, 参考文献, 附录, 致谢 | H1 |
| X. (single digit + dot at line start, e.g. "1. 系统设计") | H1 |
| X.X (e.g. "1.1", "2.3") | H2 |
| X.X.X (e.g. "3.1.2") | H3 |
| 一、二、三、... (Chinese numbered list as section title) | H1 |
| （一）（二）... | H2 |
| Short line (< 40 chars) at page top → section title | H1 or H2 |
| Long paragraph (> 100 chars), normal font → body text | Lv=0 |

## Aggressive Detection — You MUST
1. Read ALL paragraphs to understand the full document structure first
2. Check EVERY paragraph. If current level does NOT match the rules above → it's an error
3. Levels at H6, H7, H8, H9, H10 are ALWAYS wrong — fix them to appropriate H1~H4
4. A paragraph marked Lv=0 (·) that matches any heading pattern → MUST be flagged
5. A long body paragraph marked as H1~H5 → MUST be demoted to Lv=0
6. ERR ON THE SIDE OF CORRECTING. Better to flag 10 false positives than miss 1 real error
7. DO NOT return empty corrections unless EVERY single paragraph's level is perfect

## Position Cues (P=page, Y=vertical pos, H=text height)
- Page top (small Y) + new topic → likely H1
- Larger H (bigger font) → more likely a heading

## Output
Return ONLY JSON:
{"corrections": [{"index": 5, "heading_level": 1, "reason": "H10→H1: 第1章 概述，章标题必须H1"}]}

heading_level meanings:
- 0: normal body text (not a heading)
- 1: 第X章, X., 一、二、三、, independent module at page top
- 2: X.X, （一）（二）, ①
- 3: X.X.X, a. b. c.
- 4+: deeper nesting

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
            max_tokens=4096,
        )
        elapsed = time.time() - t0
        content = response.choices[0].message.content or ""
        usage = response.usage
        _log.info("[RES %s] elapsed=%.1fs tokens_in=%d tokens_out=%d",
                   request_id, elapsed,
                   usage.prompt_tokens if usage else 0,
                   usage.completion_tokens if usage else 0)
        _log.debug("[RES %s] content=%s", request_id, content[:500])

        _conv_log.info("=== RES %s elapsed=%.1fs tokens_in=%d tokens_out=%d ===",
                       request_id, elapsed,
                       usage.prompt_tokens if usage else 0,
                       usage.completion_tokens if usage else 0)
        _conv_log.info("%s", content)

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

        data = json.loads(json_str)
        corrections = data.get("corrections", [])
        _log.info("[RES %s] %d heading corrections", request_id, len(corrections))
        for c in corrections:
            _log.debug("[RES %s]   index=%d level=%d reason=%s",
                        request_id, c.get("index"), c.get("heading_level"), c.get("reason", ""))
        return corrections

    except Exception as e:
        _log.error("[ERR %s] heading detect failed: %s", request_id, e)
        return []
