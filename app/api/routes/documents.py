import logging
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_document
from app.config.settings import settings
from app.models.document import Document
from app.models.paragraph import Paragraph
from app.models.coordinate import PDFCoordinate
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.schemas.paragraph import ParagraphResponse
from app.schemas.coordinate import CoordinateResponse
from app.storage.local_fs import storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a DOCX or PDF document."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".doc", ".docx", ".pdf"):
        raise HTTPException(status_code=400, detail="Only .doc, .docx and .pdf files are supported")

    # Save file to storage
    temp_dir = settings.TEMP_DIR
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    with open(temp_path, "wb") as f:
        content = await file.read()
        f.write(content)

    storage_key = storage.save_file(temp_path, subdir="documents")
    temp_path.unlink()  # Clean up temp file

    # Create document record
    doc = Document(
        filename=file.filename,
        original_format=suffix.lstrip("."),
        storage_key=storage_key,
        status="uploaded",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return DocumentUploadResponse(
        document_id=doc.id,
        filename=doc.filename,
        status=doc.status,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_info(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Get document metadata and status."""
    doc = get_document(db, document_id)
    return doc


@router.get("/{document_id}/paragraphs", response_model=List[ParagraphResponse])
def get_paragraphs(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Get all parsed paragraphs for a document."""
    doc = get_document(db, document_id)
    paragraphs = db.query(Paragraph).filter(
        Paragraph.document_id == document_id
    ).order_by(Paragraph.para_index).all()
    return paragraphs


@router.get("/{document_id}/coordinates", response_model=List[CoordinateResponse])
def get_coordinates(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Get all PDF coordinate mappings for a document."""
    doc = get_document(db, document_id)
    coords = db.query(PDFCoordinate).filter(
        PDFCoordinate.document_id == document_id
    ).all()
    return coords


@router.get("/{document_id}/paragraphs/{paragraph_id}/coordinates", response_model=List[CoordinateResponse])
def get_paragraph_coordinates(
    document_id: str,
    paragraph_id: str,
    db: Session = Depends(get_db),
):
    """Get PDF coordinates for a specific paragraph."""
    doc = get_document(db, document_id)
    coords = db.query(PDFCoordinate).filter(
        PDFCoordinate.document_id == document_id,
        PDFCoordinate.paragraph_id == paragraph_id,
    ).all()
    return coords
