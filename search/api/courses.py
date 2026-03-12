"""Courses endpoints."""

from fastapi import APIRouter, HTTPException
from search.api.models import CourseDetail, CourseSummary, SearchResult
from search.server.tools import get_course as _get_course, list_courses as _list_courses, find_by_teacher as _find_by_teacher

router = APIRouter()


@router.get("/courses", response_model=list[CourseSummary], summary="Liste des cours")
def list_courses():
    """Retourne les 16+ cours structurés disponibles."""
    return [CourseSummary(**c) for c in _list_courses()]


@router.get("/courses/{course_id}", response_model=CourseDetail, summary="Détail d'un cours")
def get_course(course_id: str):
    """
    Retourne le curriculum complet d'un cours avec toutes ses ressources.

    Exemples : `mn`, `dn`, `sn`, `an`, `abhidhamma`, `meditation`, `pali-primer`, `bn4`
    """
    result = _get_course(course_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Cours '{course_id}' introuvable")
    return CourseDetail(**result)


@router.get("/teachers/{teacher_slug}", response_model=list[SearchResult], summary="Contenu par enseignant")
def get_teacher(teacher_slug: str, limit: int = 20):
    """
    Retourne tout le contenu d'un enseignant/auteur.

    Exemples : `bodhi`, `thanissaro`, `ajahn-chah`, `ajahn-brahm`, `analayo`, `sujato`
    """
    raw = _find_by_teacher(teacher_slug, limit=limit)
    if not raw:
        raise HTTPException(status_code=404, detail=f"Enseignant '{teacher_slug}' introuvable ou sans contenu indexé")
    return [SearchResult(score=1.0, url=r.get("url", ""), **{k: v for k, v in r.items() if k != "url"}) for r in raw]
