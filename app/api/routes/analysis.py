import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_document
from app.config.settings import settings
from app.models.document import Document
from app.models.paragraph import Paragraph, Run
from app.models.coordinate import PDFCoordinate
from app.parser.docx_parser import DocxParser
from app.render.word_renderer import render_docx_to_pdf
from app.render.pdf_parser import parse_pdf
from app.render.text_anchor import map_paragraphs_to_pdf
from app.storage.local_fs import storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["analysis"])


@router.post("/{document_id}/parse")
def parse_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Parse DOCX file and extract paragraph structure."""
    doc = get_document(db, document_id)

    if doc.status not in ("uploaded", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"Document status is '{doc.status}', expected 'uploaded' or 'error'"
        )

    # Update status
    doc.status = "parsing"
    db.commit()

    try:
        # Get file path
        file_path = storage.get_path(doc.storage_key)

        # Parse DOCX
        parser = DocxParser()
        structure = parser.parse(file_path)

        # Store paragraphs
        for para_data in structure.paragraphs:
            paragraph = Paragraph(
                document_id=document_id,
                para_index=para_data.para_index,
                style_name=para_data.style_name,
                heading_level=para_data.heading_level,
                full_text=para_data.full_text,
                xml_raw=para_data.xml_raw,
                has_highlights=para_data.has_highlights,
                has_revisions=para_data.has_revisions,
                is_deleted=para_data.is_deleted,
                is_image=para_data.is_image,
            )
            db.add(paragraph)
            db.flush()

            # Store runs
            for run_data in para_data.runs:
                run = Run(
                    paragraph_id=paragraph.id,
                    run_index=para_data.runs.index(run_data),
                    text=run_data.text,
                    is_bold=run_data.is_bold,
                    is_italic=run_data.is_italic,
                    is_highlighted=run_data.is_highlighted,
                    highlight_color=run_data.highlight_color,
                    shading_color=run_data.shading_color,
                    is_inserted=run_data.is_inserted,
                    is_deleted_text=run_data.is_deleted_text,
                    revision_author=run_data.revision_author,
                )
                db.add(run)

        doc.status = "parsed"
        db.commit()

        return {
            "status": "parsed",
            "paragraph_count": len(structure.paragraphs),
        }

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/render")
def render_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Render DOCX to PDF using Word COM."""
    doc = get_document(db, document_id)

    if doc.status not in ("parsed", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"Document status is '{doc.status}', expected 'parsed'"
        )

    doc.status = "rendering"
    db.commit()

    try:
        # Get file paths
        docx_path = storage.get_path(doc.storage_key)
        pdf_filename = Path(doc.filename).stem + ".pdf"
        pdf_path = settings.TEMP_DIR / pdf_filename

        # Render to PDF
        render_docx_to_pdf(docx_path, pdf_path)

        # Store PDF
        pdf_storage_key = storage.save_file(pdf_path, subdir="pdfs")
        pdf_path.unlink()  # Clean up temp file

        # Update document
        doc.pdf_storage_key = pdf_storage_key
        doc.status = "rendered"
        db.commit()

        return {"status": "rendered", "pdf_storage_key": pdf_storage_key}

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/align")
def align_coordinates(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Map paragraph text to PDF coordinates."""
    doc = get_document(db, document_id)

    if doc.status not in ("rendered", "error"):
        raise HTTPException(
            status_code=400,
            detail=f"Document status is '{doc.status}', expected 'rendered'"
        )

    doc.status = "aligning"
    db.commit()

    try:
        # Get paragraphs from DB
        paragraphs = db.query(Paragraph).filter(
            Paragraph.document_id == document_id
        ).order_by(Paragraph.para_index).all()

        # Get PDF path
        pdf_path = storage.get_path(doc.pdf_storage_key)

        # Map paragraphs to PDF coordinates
        para_data_list = []
        for p in paragraphs:
            from app.parser.docx_parser import ParagraphData, RunData
            para_data = ParagraphData(
                para_index=p.para_index,
                full_text=p.full_text,
                style_name=p.style_name,
                heading_level=p.heading_level,
                has_highlights=p.has_highlights,
                has_revisions=p.has_revisions,
                is_deleted=p.is_deleted,
            )
            para_data_list.append(para_data)

        mappings = map_paragraphs_to_pdf(para_data_list, str(pdf_path))

        # Store coordinate mappings
        for mapping in mappings:
            # Find the paragraph
            para = next(
                (p for p in paragraphs if p.para_index == mapping.paragraph_id),
                None
            )
            if para:
                coord = PDFCoordinate(
                    document_id=document_id,
                    paragraph_id=para.id,
                    page_number=mapping.page_number,
                    bbox_x0=mapping.bbox[0],
                    bbox_y0=mapping.bbox[1],
                    bbox_x1=mapping.bbox[2],
                    bbox_y1=mapping.bbox[3],
                    match_confidence=mapping.confidence,
                    match_strategy=mapping.strategy,
                )
                db.add(coord)

        doc.status = "aligned"
        db.commit()

        return {
            "status": "aligned",
            "mapped_count": len(mappings),
            "total_paragraphs": len(paragraphs),
        }

    except Exception as e:
        doc.status = "error"
        doc.error_message = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/full-pipeline")
def run_full_pipeline(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Run the complete pipeline: parse -> render -> align."""
    doc = get_document(db, document_id)

    # Step 1: Parse
    parse_result = parse_document(document_id, db)

    # Step 2: Render
    render_result = render_document(document_id, db)

    # Step 3: Align
    align_result = align_coordinates(document_id, db)

    return {
        "status": "aligned",
        "parse": parse_result,
        "render": render_result,
        "align": align_result,
    }
