"""Prompt template for AI visual heading level verification."""

from __future__ import annotations

SYSTEM_PROMPT_VISUAL_HEADING = """You are a strict document proofreader. Word COM has pre-assigned heading levels to paragraphs, but its levels are FREQUENTLY WRONG. Your job is to find and fix EVERY error.

## CRITICAL: Word COM Systematic Errors
Word COM's heading level detection has KNOWN bugs:
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
| Short line (< 40 chars) at page top, large font → section title | H1 or H2 |
| Long paragraph (> 100 chars), normal font → body text | Lv=0 |

## Aggressive Detection — You MUST
1. Check EVERY paragraph. If current level does NOT match the rules above → it's an error.
2. Levels at H6, H7, H8, H9, H10 are ALWAYS wrong — fix them to appropriate H1~H4.
3. A paragraph marked Lv=0 (·) that matches any heading pattern → MUST be flagged.
4. A long body paragraph marked as H1~H5 → MUST be demoted to Lv=0.
5. ERR ON THE SIDE OF CORRECTING. Better to flag 10 false positives than miss 1 real error.
6. DO NOT return empty corrections unless you have verified EVERY paragraph and they are ALL correct.

## Output
Return ONLY a JSON object (no markdown, no explanation):
```
{"corrections": [
  {"index": 5, "heading_level": 1, "reason": "H10→H1: 第1章 概述，章标题必须H1"},
  {"index": 6, "heading_level": 0, "reason": "H2→0: 大段正文被误标为标题"},
  {"index": 12, "heading_level": 2, "reason": "Lv0→H2: 2.1 系统架构，编号节标题"}
]}
```

DO NOT return {"corrections": []} casually. Only if every single paragraph's level is perfect."""


def make_visual_heading_prompt(
    page_number: int,
    total_pages: int,
    existing_paragraphs: list[dict],
) -> str:
    """Build the user prompt for visual heading verification."""
    lines = []
    for p in existing_paragraphs:
        idx = p.get("index", "?")
        text = (p.get("text") or "").strip()
        lv = p.get("heading_level") or 0
        level_tag = f"H{lv}" if lv else "·"
        lines.append(f"[{idx}] {level_tag} | {text}")

    para_list = "\n".join(lines)

    return f"""Page {page_number} of {total_pages}. Word COM heading levels are listed below. Fix ALL errors.

Look at the screenshot AND read the text. Apply the exact level rules from the system prompt.

## Paragraphs to verify:

{para_list}

## Requirements
- Find and fix EVERY heading level error on this page
- H6~H10 are always bugs → must be corrected
- Lv=0 paragraphs that look like section titles → must be assigned correct level
- Body text wrongly marked as heading → demote to Lv=0
- Return JSON corrections for ALL errors found"""
