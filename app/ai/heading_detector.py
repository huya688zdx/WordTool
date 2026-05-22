"""AI-assisted heading level detection and correction."""

from __future__ import annotations

import json
import re
import time

from app.ai import get_ai_logger, get_conv_logger

_log = get_ai_logger()
_conv_log = get_conv_logger()

HEADING_DETECT_PROMPT = """You are a document structure analyst. Review paragraphs from a Chinese technical document and identify ones that SHOULD be headings but are currently marked as · (normal text, Lv=0).

You will receive each paragraph with its text, existing heading level, and pre-detected page position (P=page, Y=vertical position, H=text height from Word COM). Use BOTH text content AND position cues to judge heading levels.

## Chinese Document Patterns You MUST Check
- "第X章 ..." → heading_level 1
- "X. ...", "X.X ...", "X.X.X ..." at line start → heading_level 1/2/3 by dot count
- "一、", "二、", "三、" → heading_level 1
- "（一）", "（二）" → heading_level 2
- Any short line (≤40 chars) that names a section topic with no body text around it → heading
- Lines like 概述, 背景, 目的, 范围, 总结, 需求分析, 系统设计, 接口定义, 数据结构, 测试方案, 部署方案

## Position Cues (P=page, Y=top position, H=height)
- Page top (small Y) + new topic → likely H1
- Larger H (bigger font) → more likely a heading
- A standalone independent module at page top → H1, even without "第X章" prefix

## Rules
1. Scan EVERY paragraph marked as · (Lv=0)
2. If it matches ANY heading pattern → MUST include in corrections
3. ERR ON MARKING — better to flag a borderline case than miss a real heading
4. Use position cues: a paragraph at page top starting a new topic IS a heading

## Output
Return ONLY JSON: {"corrections": [{"index": 5, "heading_level": 2, "reason": "2.1 系统架构 at page top"}]}

heading_level meanings:
- 1: 第X章, X., 一、二、三、, independent module at page top
- 2: X.X, （一）（二）, ①
- 3: X.X.X, a. b. c.

Return {"corrections": []} ONLY if truly no missed headings. Double-check before empty."""


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

    user_prompt = f"""Analyze {len(paragraphs)} paragraphs from a Chinese technical document.

Format: [index] marker P? Y? H? | full_text
  H1/H2/H3 = existing heading
  · = normal text (check these!)
{pos_hint}
{para_text}

## Constraints
- A standalone/independent module section (even without "第X章" or "X." prefix) → heading_level 1
- Paragraphs that clearly start a new topic, especially near page top → likely H1

Find ALL · (Lv=0) paragraphs that look like headings.
Return ONLY JSON corrections."""

    from app.ai import make_http_client
    client = OpenAI(api_key=api_key, base_url=base_url, http_client=make_http_client())
    request_id = f"heading-{int(time.time() * 1000)}"
    _log.info("[REQ %s] model=%s base_url=%s paragraphs=%d", request_id, model, base_url, len(paragraphs))
    _log.debug("[REQ %s] system_prompt=%s", request_id, HEADING_DETECT_PROMPT[:200])
    _log.debug("[REQ %s] user_prompt=%s", request_id, user_prompt[:500])

    # Full conversation log
    _conv_log.info("=== REQ %s ===", request_id)
    _conv_log.info("model=%s base_url=%s paragraphs=%d", model, base_url, len(paragraphs))
    _conv_log.debug("--- system ---\n%s", HEADING_DETECT_PROMPT)
    _conv_log.debug("--- user ---\n%s", user_prompt)

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
        _conv_log.debug("%s", content)

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
