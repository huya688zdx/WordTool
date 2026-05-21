"""AI-assisted heading level detection and correction.

When documents have visually-styled headings that aren't marked with
proper Word heading styles, this module sends the paragraph list to
an LLM to detect and correct heading levels based on content patterns.
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path

_log = logging.getLogger(__name__)

HEADING_DETECT_PROMPT = """You are a document structure analyst. Your task is to review a list of paragraphs extracted from a document and identify paragraphs that SHOULD be headings but are currently marked as normal text.

## How to Identify Headings
Look for these patterns in paragraph content:
1. **Numbering**: lines starting with "第X章", "一、", "1.", "1.1", "（一）", "①", etc.
2. **Short & formal**: standalone short lines (<=30 chars) that summarize a topic
3. **Structural keywords**: lines containing "概述", "总结", "目的", "范围", "背景", etc. that appear to introduce sections
4. **Pattern consistency**: if a document uses "X.X" numbering for headings, all such lines should be headings
5. **Context contrast**: a short line followed by multiple longer body paragraphs is likely a heading

## What NOT to Mark as Heading
- Body paragraphs (>100 chars of continuous text)
- Table of contents entries
- Image captions
- Page numbers or headers/footers

## Output Format
Return ONLY a JSON object:
```
{
  "corrections": [
    {"index": 5, "heading_level": 1, "reason": "第2章 系统设计"},
    {"index": 8, "heading_level": 2, "reason": "2.1 模块划分"},
    {"index": 15, "heading_level": 2, "reason": "2.2 接口定义"}
  ]
}
```

Only include paragraphs that need CORRECTION (heading_level changed from current). Use:
- heading_level 1: major chapters (第X章, X., 一、)
- heading_level 2: sections (X.X, (一), etc.)
- heading_level 3: subsections (X.X.X, ①, etc.)

If all headings are already correct, return {"corrections": []}."""


def detect_headings(
    api_key: str, base_url: str, model: str,
    paragraphs: list[dict],
) -> list[dict]:
    """Send paragraph list to AI for heading level analysis.

    Args:
        paragraphs: [{"index": int, "heading_level": int|None, "text": str}, ...]

    Returns:
        List of corrections: [{"index": int, "heading_level": int, "reason": str}, ...]
    """
    from openai import OpenAI

    # Build a compact representation: index, current level, first 80 chars
    lines = []
    for p in paragraphs:
        level = p.get("heading_level") or 0
        text = (p.get("text") or "")[:80]
        lines.append(f"[{p['index']}] Lv={level} | {text}")

    para_text = "\n".join(lines)
    user_prompt = f"""Review these {len(paragraphs)} paragraphs and identify any that should be headings but aren't marked correctly.

Current paragraph list (index, current level, text):
{para_text}

Return ONLY the JSON corrections. No other text."""

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
            temperature=0.1,
            max_tokens=4096,
        )
        elapsed = time.time() - t0
        content = response.choices[0].message.content or ""
        _log.info("AI heading detect: %.1fs, response=%s", elapsed, content[:200])

        # Parse JSON response
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            json_str = content[brace_start:brace_end + 1] if brace_start >= 0 else content

        data = json.loads(json_str)
        corrections = data.get("corrections", [])
        _log.info("AI heading detect: %d corrections suggested", len(corrections))
        return corrections

    except Exception as e:
        _log.error("AI heading detect failed: %s", e)
        return []
