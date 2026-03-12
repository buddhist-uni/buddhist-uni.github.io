"""Search and reading-path endpoints."""

from fastapi import APIRouter, Query as QParam
from search.api.models import SearchResponse, SearchResult, ReadingPathItem
from search.server.tools import search_dharma as _search, get_reading_path as _path

router = APIRouter()


@router.get("/search", response_model=SearchResponse, summary="Recherche sémantique")
def search(
    q: str = QParam(..., description="Requête en langage naturel", min_length=2),
    tags: list[str] = QParam(default=[], description="Filtrer par tags (ex: nibbana, pali)"),
    category: str | None = QParam(default=None, description="articles|canon|av|booklets|essays|monographs|papers|excerpts|reference"),
    course: str | None = QParam(default=None, description="Slug du cours (ex: mn, abhidhamma)"),
    min_stars: int | None = QParam(default=None, ge=1, le=5, description="Qualité minimale 1-5"),
    limit: int = QParam(default=8, ge=1, le=20),
):
    """
    Recherche sémantique dans les 4494+ ressources bouddhistes.

    Exemples :
    - `/search?q=impermanence+nibbana`
    - `/search?q=meditation+breath&category=av&min_stars=4`
    - `/search?q=pali+grammar&tags=pali&tags=language`
    """
    raw = _search(
        query=q,
        tags=tags or None,
        category=category,
        course=course,
        limit=limit,
        min_stars=min_stars,
    )
    return SearchResponse(
        query=q,
        total=len(raw),
        results=[SearchResult(**r) for r in raw],
    )


@router.get("/reading-path", response_model=list[ReadingPathItem], summary="Parcours de lecture")
def reading_path(
    topic: str = QParam(..., description="Sujet à explorer (ex: karuna, dependent origination)"),
    level: str = QParam(default="beginner", pattern="^(beginner|intermediate|advanced)$"),
    limit: int = QParam(default=10, ge=1, le=20),
):
    """
    Génère un parcours de lecture progressif sur un sujet bouddhiste.

    - `beginner` → AV + booklets en priorité
    - `intermediate` → articles + monographs
    - `advanced` → papers + canon
    """
    raw = _path(topic=topic, level=level, limit=limit)
    return [ReadingPathItem(**r) for r in raw]
