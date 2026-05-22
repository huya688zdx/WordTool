"""Prompt template for AI-assisted page layout verification."""

from __future__ import annotations

SYSTEM_PROMPT_LAYOUT = """You are a document layout verification expert. Your task is to verify and correct paragraph bounding boxes on a document page image.

## Your Task
You will receive:
1. A screenshot of a document page
2. A list of pre-detected paragraphs with their bounding boxes and text content (from Word COM)

For each paragraph, compare its bounding box against the actual text visible in the image. If the box correctly bounds the text, keep it. If it's shifted, too small, too large, or wrong in any way — CORRECT IT.

## Critical Rules
1. **FULL text width**: The bbox must include the ENTIRE horizontal span of text — do NOT cut off text on left or right.
2. **FULL paragraph height**: Include ALL lines belonging to the same paragraph.
3. **Exclude headers and footers**: Skip page numbers, headers, footers.
4. **Image/diagram regions**: Mark as type "image".
5. **Keep existing paragraphs that look correct** — only fix the ones with visible errors.
6. **If a pre-detected paragraph's text doesn't match what you see** in the image, adjust the bbox to match the actual visible text.

## Output Format
Return ONLY a JSON object:
```
{
  "paragraphs": [
    {
      "index": 0,
      "type": "text",
      "x0_pct": 0.12,
      "y0_pct": 0.15,
      "x1_pct": 0.88,
      "y1_pct": 0.25,
      "content_preview": "First few words...",
      "corrected": false,
      "correction_note": ""
    }
  ]
}
```

- x0_pct, x1_pct: 0.0 (left) to 1.0 (right of PAGE)
- y0_pct, y1_pct: 0.0 (top) to 1.0 (bottom of PAGE)
- "corrected": true if you changed the bbox, false if the original was correct
- "correction_note": brief explanation if corrected, empty string if not
- Sort by y0_pct ascending
- Include EVERY paragraph from the input list — do not drop any"""


def make_layout_prompt(
    page_number: int,
    total_pages: int,
    doc_hint: str = "",
    existing_paragraphs: list[dict] | None = None,
) -> str:
    """Build the user prompt for layout verification.

    Args:
        page_number: Current page number (1-based)
        total_pages: Total pages in document
        doc_hint: Optional hint about document content
        existing_paragraphs: List of pre-detected paragraphs from Word COM.
            Each dict: index, text, x0_pct, y0_pct, x1_pct, y1_pct, heading_level
    """
    hint = ""
    if doc_hint:
        hint = f"\nDocument type hint: {doc_hint}"

    para_list = ""
    if existing_paragraphs:
        lines = []
        for p in existing_paragraphs:
            idx = p.get("index", "?")
            text = (p.get("text") or "").strip()[:80]
            lv = p.get("heading_level") or 0
            level_tag = f"H{lv}" if lv else "·"
            lines.append(
                f"  [{idx}] {level_tag} "
                f"x0={p.get('x0_pct', 0):.3f} y0={p.get('y0_pct', 0):.3f} "
                f"x1={p.get('x1_pct', 0):.3f} y1={p.get('y1_pct', 0):.3f} "
                f"| {text}"
            )
        para_list = "\n".join(lines)

    return f"""Verify and correct the paragraph bounding boxes on this page.

Page: {page_number} / {total_pages}{hint}

## Pre-detected paragraphs (Word COM) — verify against the image:

{para_list}

For each paragraph above:
- Check if the bbox correctly covers the visible text in the image
- If correct → keep as-is, set corrected=false
- If wrong → fix the coordinates, set corrected=true, add a short note

Return ONLY the JSON output. Include ALL paragraphs from the list above."""
