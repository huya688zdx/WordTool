from typing import Generator

from sqlalchemy.orm import Session

from app.models.base import get_session_factory
from app.models.document import Document


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for database sessions."""
    factory = get_session_factory()
    db = factory()
    try:
        yield db
    finally:
        db.close()


def get_document(db: Session, document_id: str) -> Document:
    """Get document by ID or raise 404."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if doc is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Document not found")
    return doc
