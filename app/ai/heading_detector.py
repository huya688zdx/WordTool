"""AI-assisted heading level detection and correction."""

from __future__ import annotations

import json
import logging
import re
import time

_log = logging.getLogger(__name__)

HEADING_DETECT_PROMPT = """You are a document structure analyst. Review paragraphs from a Chinese technical document and identify ones that SHOULD be headings but are currently marked as · (normal text, Lv=0).

## Chinese Document Patterns You MUST Check
- "第X章 ..." → heading_level 1
- "X. ...", "X.X ...", "X.X.X ..." at line start → heading_level 1/2/3 by dot count
- "一、", "二、", "三、" → heading_level 1
- "（一）", "（二）" → heading_level 2
- Any short line (≤40 chars) that names a section topic with no body text around it → heading
- Lines like 概述, 背景, 目的, 范围, 总结, 需求分析, 系统设计, 接口定义, 数据结构, 测试方案, 部署方案

## Rules
1. Scan EVERY paragraph marked as · (Lv=0)
2. If it matches ANY heading pattern → MUST include in corrections
3. ERR ON MARKING — better to flag a borderline case than miss a real heading

## Output
Return ONLY JSON: {"corrections": [{"index": 5, "heading_level": 2, "reason": "2.1 系统架构"}]}

heading_level meanings:
- 1: 第X章, X., 一、二、三、
- 2: X.X, （一）（二）, ①
- 3: X.X.X, a. b. c.

Return {"corrections": []} ONLY if truly no missed headings. Double-check before empty."""


def detect_headings(
    api_key: str, base_url: str, model: str,
    paragraphs: list[dict],
) -> list[dict]:
    """Send paragraph list to AI for heading level analysis."""
    from openai import OpenAI

    # Build clear representation: numbered index, level marker, FULL text
    lines = []
    for p in paragraphs:
        level = p.get("heading_level") or 0
        text = (p.get("text") or "").strip()
        marker = f"H{level}" if level > 0 else " · "
        lines.append(f"[{p['index']:04d}] {marker} | {text}")

    para_text = "\n".join(lines)
    user_prompt = f"""Analyze {len(paragraphs)} paragraphs from a Chinese technical document.

Format: [index] marker | full_text
  H1/H2/H3 = existing heading
  · = normal text (check these!)

{para_text}

Find ALL · (Lv=0) paragraphs that look like headings.
Return ONLY JSON corrections."""

    client = OpenAI(api_key=api_key, base_url=base_url)
    _log.info("AI heading detect: sending %d paragraphs to %s", len(paragraphs), model)

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
        _log.info("AI heading detect: %.1fs, response: %s", elapsed, content[:300])

        # Parse JSON
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            json_str = content[brace_start:brace_end + 1] if brace_start >= 0 else content

        data = json.loads(json_str)
        corrections = data.get("corrections", [])
        _log.info("AI heading detect: %d corrections", len(corrections))
        return corrections

    except Exception as e:
        _log.error("AI heading detect failed: %s", e)
        return []
