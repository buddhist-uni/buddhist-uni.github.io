"""
Buddhist University Search API — FastAPI app.

Usage:
    PYTHONPATH=/path/to/buddhist-uni.github.io \\
        uvicorn search.api.main:app --port 8001 --reload

Docs:
    http://localhost:8001/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from search.api.search import router as search_router
from search.api.courses import router as courses_router

app = FastAPI(
    title="Buddhist University Search API",
    description=(
        "Recherche sémantique dans 4494+ ressources bouddhistes — "
        "textes canoniques, articles académiques, AV, cours structurés."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(search_router, tags=["Search"])
app.include_router(courses_router, tags=["Courses"])


@app.get("/", tags=["Health"])
def root():
    return {
        "name": "Buddhist University Search API",
        "version": "1.0.0",
        "docs": "/docs",
        "endpoints": {
            "search": "GET /search?q=...&tags=...&category=...&limit=8",
            "reading_path": "GET /reading-path?topic=...&level=beginner",
            "courses": "GET /courses",
            "course_detail": "GET /courses/{id}",
            "teacher": "GET /teachers/{slug}",
        },
    }


@app.get("/health", tags=["Health"])
def health():
    from search.ingestion.qdrant_setup import get_client, COLLECTION_NAME
    client = get_client()
    info = client.get_collection(COLLECTION_NAME)
    return {
        "status": "ok",
        "indexed_documents": info.points_count,
        "collection": COLLECTION_NAME,
    }
