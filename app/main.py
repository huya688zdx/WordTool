from contextlib import asynccontextmanager
from fastapi import FastAPI

from app.config.settings import settings
from app.config.logging import setup_logging
from app.models.base import init_db
from app.api.routes import documents, analysis


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    init_db()
    yield


app = FastAPI(title="WordAgent", version="0.1.0", lifespan=lifespan)

# Include routers
app.include_router(documents.router)
app.include_router(analysis.router)


@app.get("/health")
def health():
    return {"status": "ok"}
