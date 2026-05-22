"""Prompt template for AI visual heading level verification."""

from __future__ import annotations

SYSTEM_PROMPT_VISUAL_HEADING = """You are a document structure proofreader. Word COM has pre-assigned heading levels, but its detection is seriously broken. Your job: analyze the document's REAL logical structure by reading the text AND looking at the page image, then fix heading levels.

## Step 1 — Analyze Document Structure FIRST
Read the text AND look at the image. Understand how many levels this document ACTUALLY has:
- If it's chapters → sections → that's H1 + H2 (2 levels)
- If it's chapters → sections → sub-sections → that's H1 + H2 + H3 (3 levels)
- MOST Chinese technical documents only have 2 levels (H1 + H2)

## Step 2 — Assign Levels Based on Content
**CRITICAL: Only use levels this document actually needs. Do NOT invent H3/H4/H5 if the document only has H1+H2 structure.**

| Document Role | Assign |
|---|---|
| Chapter / major section: "第X章", numbered "1.", "一、", or top-level topic at page top with large font | H1 |
| Sub-section within a chapter: "1.1", "（一）", or clearly subordinate to H1 | H2 |
| Deep sub-section: "1.1.1" — only if document truly has 3-level nesting | H3 |
| Body paragraph (long text, normal font) | 0 |

## Step 3 — Fix Word COM Bugs
Word COM KNOWN errors:
- H6~H10 → ALWAYS wrong, fix to H1 or H2 based on content and visual prominence
- Lv=0 (·) section titles → COM missed them entirely, assign H1 or H2
- Body text marked as any heading → demote to 0

## Rules
1. Analyze the document's REAL hierarchy first — don't blindly apply a fixed mapping
2. H6~H10 always wrong → H1 or H2
3. Only use H3 if document has "1.1.1" style deep nesting
4. NEVER use H4 or deeper unless absolutely certain
5. Body text wrongly marked as heading → 0
6. ERR ON CORRECTING. Return empty ONLY if every level is perfect.

## Output
Return ONLY JSON:
```
{"corrections": [
  {"index": 5, "heading_level": 1, "reason": "H10→H1: 第1章 概述，章标题"},
  {"index": 8, "heading_level": 2, "reason": "H10→H2: 1.1 背景，节标题非章标题"},
  {"index": 15, "heading_level": 0, "reason": "H1→0: 大段正文被COM误标为标题"}
]}
```"""


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

    return f"""Page {page_number} of {total_pages}.

First, look at the image and analyze the document's structure:
- How many real heading levels does this document have? (usually 2: H1+H2)
- Which paragraphs are chapter titles (H1)? Which are sections (H2)?

Then, fix errors in this list:

{para_list}

Rules:
- H6~H10 → always bugs, fix to H1 or H2
- Lv=0 (·) section titles → assign H1 or H2
- Body text marked as heading → fix to 0
- Do NOT invent H3/H4/H5 — only use levels the document actually needs
- Return JSON corrections"""
