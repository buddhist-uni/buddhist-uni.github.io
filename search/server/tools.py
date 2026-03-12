"""
Core search tools used by both the MCP server and the FastAPI.
All functions query Qdrant directly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import frontmatter
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue, MatchAny

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from search.ingestion.qdrant_setup import COLLECTION_NAME, QDRANT_URL
from search.ingestion.embedder import get_embedder

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=QDRANT_URL)
    return _client


def _build_filter(
    tags: list[str] | None = None,
    category: str | None = None,
    course: str | None = None,
    min_stars: int | None = None,
) -> Filter | None:
    conditions = []

    if tags:
        conditions.append(FieldCondition(key="tags", match=MatchAny(any=tags)))
    if category:
        conditions.append(FieldCondition(key="category", match=MatchValue(value=category)))
    if course:
        conditions.append(FieldCondition(key="course", match=MatchValue(value=course)))
    if min_stars:
        from qdrant_client.models import Range
        conditions.append(FieldCondition(key="stars", range=Range(gte=min_stars)))

    return Filter(must=conditions) if conditions else None


def search_dharma(
    query: str,
    tags: list[str] | None = None,
    category: str | None = None,
    course: str | None = None,
    limit: int = 8,
    min_stars: int | None = None,
) -> list[dict]:
    """
    Semantic search across 4494+ Buddhist texts, scriptures, audio/video, and courses.

    Args:
        query: Natural language query (e.g. "what is anatta?", "meditation on breath")
        tags: Filter by topic tags (e.g. ["impermanence", "nibbana"])
        category: Filter by content type: articles, canon, av, booklets, essays,
                  monographs, papers, excerpts, reference
        course: Filter by course slug (e.g. "mn", "abhidhamma", "meditation")
        limit: Number of results (default 8, max 20)
        min_stars: Minimum quality score 1-5 (5 = featured content)

    Returns:
        List of matching content with score, title, URL, authors, tags, category
    """
    embedder = get_embedder()
    client = get_client()

    query_vector = embedder.encode_query(query)
    qdrant_filter = _build_filter(tags=tags, category=category, course=course, min_stars=min_stars)

    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=query_vector,
        query_filter=qdrant_filter,
        limit=min(limit, 20),
        with_payload=True,
    ).points

    return [
        {
            "score": round(hit.score, 4),
            "title": hit.payload.get("title", ""),
            "category": hit.payload.get("category", ""),
            "tags": hit.payload.get("tags", []),
            "authors": hit.payload.get("authors", []),
            "course": hit.payload.get("course"),
            "year": hit.payload.get("year"),
            "stars": hit.payload.get("stars"),
            "url": hit.payload.get("url", ""),
            "external_url": hit.payload.get("external_url"),
            "minutes": hit.payload.get("minutes"),
            "pages": hit.payload.get("pages"),
        }
        for hit in results
    ]


def get_course(course_id: str) -> dict | None:
    """
    Get the full curriculum of a structured learning course.

    Args:
        course_id: Course slug (e.g. "mn", "abhidhamma", "meditation", "pali-primer", "bn4")

    Returns:
        Course metadata + ordered list of content items
    """
    courses_dir = PROJECT_ROOT / "_courses"
    course_file = courses_dir / f"{course_id}.md"

    if not course_file.exists():
        # Try to find by partial match
        matches = list(courses_dir.glob(f"*{course_id}*.md"))
        if not matches:
            return None
        course_file = matches[0]
        course_id = course_file.stem

    post = frontmatter.load(str(course_file))
    meta = post.metadata

    # Search all content belonging to this course
    client = get_client()

    course_content = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[FieldCondition(key="course", match=MatchValue(value=course_id))]
        ),
        limit=200,
        with_payload=True,
    )[0]

    # Sort by year (ascending) for a natural reading order
    items = sorted(
        [
            {
                "title": p.payload.get("title", ""),
                "category": p.payload.get("category", ""),
                "tags": p.payload.get("tags", []),
                "authors": p.payload.get("authors", []),
                "year": p.payload.get("year"),
                "stars": p.payload.get("stars", 3),
                "url": p.payload.get("url", ""),
                "minutes": p.payload.get("minutes"),
                "pages": p.payload.get("pages"),
            }
            for p in course_content
        ],
        key=lambda x: (-(x.get("stars") or 0), x.get("year") or 9999),
    )

    return {
        "id": course_id,
        "title": str(meta.get("title", course_id)),
        "subtitle": str(meta.get("subtitle", "")),
        "description": post.content[:500] if post.content else "",
        "icon": meta.get("icon", ""),
        "next_courses": meta.get("next_courses", []),
        "content_count": len(items),
        "content": items,
    }


def list_courses() -> list[dict]:
    """List all available courses with basic metadata."""
    courses_dir = PROJECT_ROOT / "_courses"
    courses = []

    for course_file in sorted(courses_dir.glob("*.md")):
        try:
            post = frontmatter.load(str(course_file))
            meta = post.metadata
            courses.append({
                "id": course_file.stem,
                "title": str(meta.get("title", course_file.stem)),
                "subtitle": str(meta.get("subtitle", "")),
                "icon": meta.get("icon", ""),
                "next_courses": meta.get("next_courses", []),
            })
        except Exception:
            pass

    return courses


def find_by_teacher(teacher_slug: str, limit: int = 20) -> list[dict]:
    """
    Find all content by a specific teacher/author.

    Args:
        teacher_slug: Author slug (e.g. "bodhi", "ajahn-chah", "thanissaro")

    Returns:
        List of content items by this author
    """
    client = get_client()

    results = client.scroll(
        collection_name=COLLECTION_NAME,
        scroll_filter=Filter(
            must=[FieldCondition(key="authors", match=MatchValue(value=teacher_slug))]
        ),
        limit=limit,
        with_payload=True,
    )[0]

    return sorted(
        [
            {
                "title": p.payload.get("title", ""),
                "category": p.payload.get("category", ""),
                "tags": p.payload.get("tags", []),
                "year": p.payload.get("year"),
                "stars": p.payload.get("stars", 3),
                "url": p.payload.get("url", ""),
            }
            for p in results
        ],
        key=lambda x: -(x.get("stars") or 0),
    )


def get_reading_path(topic: str, level: str = "beginner", limit: int = 10) -> list[dict]:
    """
    Generate a personalized reading path on a Buddhist topic.

    Combines semantic search with quality scoring to build a progressive path
    from foundational to advanced content.

    Args:
        topic: Topic to explore (e.g. "meditation", "dependent origination", "karuna")
        level: "beginner", "intermediate", or "advanced"
        limit: Number of items in the path

    Returns:
        Ordered list of content items forming a learning path
    """
    # Level → quality/format preferences
    level_config = {
        "beginner": {"min_stars": 4, "preferred_categories": ["av", "booklets", "essays"]},
        "intermediate": {"min_stars": 3, "preferred_categories": ["articles", "monographs", "booklets"]},
        "advanced": {"min_stars": 3, "preferred_categories": ["articles", "papers", "canon"]},
    }
    config = level_config.get(level, level_config["beginner"])

    # Search broadly
    all_results = search_dharma(query=topic, limit=limit * 3, min_stars=config["min_stars"])

    if not all_results:
        all_results = search_dharma(query=topic, limit=limit * 2)

    # Score and sort: prefer level-appropriate categories
    preferred = config["preferred_categories"]

    def path_score(item: dict) -> tuple:
        cat_bonus = 1 if item.get("category") in preferred else 0
        stars = item.get("stars") or 3
        sem_score = item.get("score") or 0
        return (-cat_bonus, -stars, -sem_score)  # negate for ascending sort

    sorted_results = sorted(all_results, key=path_score)[:limit]

    # Add ordering metadata
    for i, item in enumerate(sorted_results, 1):
        item["path_order"] = i
        item["level"] = level

    return sorted_results
