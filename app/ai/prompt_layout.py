"""Prompt template for AI visual heading level verification."""

from __future__ import annotations

SYSTEM_PROMPT_VISUAL_HEADING = """You are a document structure analyst with vision capability. You will receive a page screenshot AND the text content of every paragraph on that page, along with Word COM's pre-assigned heading levels.

## Your ONLY Task
For each paragraph on this page, check whether its heading_level is CORRECT.
- Word COM often assigns WRONG levels (e.g., H10 for a chapter title that should be H1)
- Use the VISUAL layout (font size, boldness, position on page) AND text content to judge
- Only flag paragraphs whose level is WRONG — do not include correct ones

## What to Check
1. **Visual cues**: Large/bold text at page top → likely H1; indented smaller text → H2/H3
2. **Text patterns**: "第X章", "一、", "X.X" → heading; check level matches pattern
3. **Body text**: Long paragraphs of normal-sized text → should be Lv=0 (not a heading)
4. **Wrong levels**: H10 where H1 belongs, H5 where H2 belongs, · where a heading should be

## Output Format
Return ONLY a JSON object:
```
{"corrections": [
  {"index": 5, "heading_level": 1, "reason": "H10→H1: 章标题，大号加粗居页面顶部"},
  {"index": 12, "heading_level": 2, "reason": "·→H2: 2.1 系统架构，COM遗漏"}
]}
```

- "index": paragraph index from the input
- "heading_level": the CORRECT level (0 = normal body text)
- "reason": explain what was wrong and why you changed it

Include ONLY paragraphs whose heading_level needs correction.
Return {"corrections": []} if all levels are correct.

IMPORTANT: Do NOT return coordinates or bounding boxes. Only return heading level corrections."""


def make_visual_heading_prompt(
    page_number: int,
    total_pages: int,
    existing_paragraphs: list[dict],
) -> str:
    """Build the user prompt for visual heading verification.

    Args:
        page_number: Current page number (1-based)
        total_pages: Total pages in document
        existing_paragraphs: List of paragraphs on this page.
            Each dict: index, text, heading_level
    """
    lines = []
    for p in existing_paragraphs:
        idx = p.get("index", "?")
        text = (p.get("text") or "").strip()
        lv = p.get("heading_level") or 0
        level_tag = f"H{lv}" if lv else "·"
        lines.append(f"[{idx}] {level_tag} | {text}")

    para_list = "\n".join(lines)

    return f"""Verify heading levels for every paragraph on this page.

Page: {page_number} / {total_pages}

Look at the page image AND read the text below. For each paragraph, check if its heading_level is correct.

## Paragraphs on this page (with Word COM levels):

{para_list}

## Instructions
1. Look at the image: which paragraphs are visually prominent (large font, bold, at page top)?
2. Read the text: which paragraphs are chapter/section titles vs. body text?
3. Flag EVERY paragraph whose heading_level is WRONG
4. Return ONLY a JSON corrections list — no coordinates, no bounding boxes"""
