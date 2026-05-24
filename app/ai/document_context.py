from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.base import get_session_factory
from app.models.document import Document
from app.models.paragraph import Paragraph


CONTEXT_DIR = Path("./data/ai_context")


def build_document_context(document_id: str) -> dict[str, Any]:
    """Build and cache a compact document context for repeated AI calls."""
    db = get_session_factory()()
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            return {}
        paragraphs = db.query(Paragraph).filter(
            Paragraph.document_id == document_id
        ).order_by(Paragraph.para_index).all()

        outline = []
        changes = []
        change_no = 1
        for para in paragraphs:
            if para.heading_level:
                outline.append({
                    "id": f"SEC-{para.para_index:03d}",
                    "para_index": para.para_index,
                    "level": para.heading_level,
                    "title": para.full_text[:160],
                })

            changed_text = para.changed_text or para.highlighted_text
            is_change = bool(para.has_highlights or para.has_revisions or changed_text)
            if is_change:
                change_id = f"CHG-{change_no:03d}"
                change_no += 1
                changes.append({
                    "id": change_id,
                    "paragraph_id": para.id,
                    "para_index": para.para_index,
                    "text": para.full_text[:500],
                    "changed_text": changed_text[:300],
                    "has_highlights": para.has_highlights,
                    "has_revisions": para.has_revisions,
                })

        context = {
            "document_id": doc.id,
            "filename": doc.filename,
            "outline": outline,
            "changes": changes,
        }
        _save_context(doc.id, context)
        return context
    finally:
        db.close()


def load_document_context(document_id: str) -> dict[str, Any]:
    path = CONTEXT_DIR / f"{document_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return build_document_context(document_id)


def find_change_for_paragraph(context: dict[str, Any], paragraph_id: str) -> dict[str, Any] | None:
    for change in context.get("changes", []):
        if change.get("paragraph_id") == paragraph_id:
            return change
    return None


def format_selected_context(
    context: dict[str, Any],
    label: str,
    selected_text: str,
) -> str:
    """Compact prompt prefix for the selected change without resending the whole doc."""
    outline = context.get("outline", [])
    outline_text = "\n".join(
        f"{item['id']} H{item['level']} {item['title']}"
        for item in outline[:80]
    )
    change_text = "\n".join(
        f"{item['id']} P{item['para_index']}: {item.get('changed_text') or item.get('text', '')[:120]}"
        for item in context.get("changes", [])[:80]
    )
    return (
        f"Document: {context.get('filename', '')}\n"
        f"Selected change: {label}\n\n"
        f"Document outline:\n{outline_text}\n\n"
        f"Known change points:\n{change_text}\n\n"
        f"Selected text:\n{selected_text}"
    )


def _save_context(document_id: str, context: dict[str, Any]) -> None:
    CONTEXT_DIR.mkdir(parents=True, exist_ok=True)
    (CONTEXT_DIR / f"{document_id}.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
