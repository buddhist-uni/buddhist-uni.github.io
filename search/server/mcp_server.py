"""
Buddhist University MCP Server
Exposes 4494+ Buddhist texts, scriptures, and courses to Claude via MCP tools.

Usage:
    python -m search.server.mcp_server

Config in .mcp.json:
    {
      "mcpServers": {
        "buddhist-uni": {
          "command": "/path/to/search/.venv/bin/python",
          "args": ["-m", "search.server.mcp_server"],
          "env": {"PYTHONPATH": "/path/to/buddhist-uni.github.io"}
        }
      }
    }
"""

from mcp.server.fastmcp import FastMCP
from search.server.tools import (
    search_dharma as _search_dharma,
    get_course as _get_course,
    list_courses as _list_courses,
    find_by_teacher as _find_by_teacher,
    get_reading_path as _get_reading_path,
)

mcp = FastMCP(
    name="buddhist-uni",
    instructions=(
        "You have access to the Buddhist University library — 4494+ texts covering "
        "Theravāda, Mahāyāna, and Vajrayāna Buddhism: Pāli canon suttas, academic articles, "
        "books, audio/video lectures, and 20+ structured courses. "
        "Use search_dharma for semantic queries, get_course for curriculum, "
        "find_by_teacher for specific teachers, get_reading_path for learning journeys."
    ),
)


@mcp.tool()
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

    Categories: articles, canon, av, booklets, essays, monographs, papers, excerpts, reference
    Tags examples: impermanence, nibbana, meditation, pali, dependent-origination, karuna,
                   mindfulness, metta, vipassana, theravada, mahayana, zen, tibetan
    Course examples: mn (Majjhima Nikāya), dn, sn, an, dhammapada, abhidhamma,
                     pali-primer, meditation, bn4, philosophy
    Stars: 1-5 quality score (5 = featured/highly recommended, 4 = recommended)

    Args:
        query: Natural language query — ask anything about Buddhism
        tags: Filter by topic tags (e.g. ["impermanence", "nibbana"])
        category: Filter by content type
        course: Filter by course slug
        limit: Number of results (default 8, max 20)
        min_stars: Minimum quality score 1-5
    """
    return _search_dharma(
        query=query,
        tags=tags,
        category=category,
        course=course,
        limit=limit,
        min_stars=min_stars,
    )


@mcp.tool()
def get_course(course_id: str) -> dict | None:
    """
    Get the full curriculum of a structured learning course.

    Available courses include:
    - mn: Majjhima Nikāya (Middle-Length Discourses)
    - dn: Dīgha Nikāya (Long Discourses)
    - sn: Saṁyutta Nikāya (Connected Discourses)
    - an: Aṅguttara Nikāya (Numerical Discourses)
    - dhammapada: The Dhammapada
    - abhidhamma: Abhidhamma studies
    - pali-primer: Introduction to Pāli language
    - meditation: Meditation practice
    - bn4: Buddhism for Beginners
    - philosophy: Buddhist philosophy
    - and many more...

    Args:
        course_id: Course slug (e.g. "mn", "abhidhamma", "meditation")

    Returns:
        Course metadata + ordered list of content items
    """
    return _get_course(course_id)


@mcp.tool()
def list_courses() -> list[dict]:
    """
    List all available structured courses at Buddhist University.
    Returns course IDs, titles, subtitles, and prerequisite chains.
    """
    return _list_courses()


@mcp.tool()
def find_by_teacher(teacher_slug: str, limit: int = 20) -> list[dict]:
    """
    Find all content by a specific Buddhist teacher or scholar.

    Teacher slug examples:
    - bodhi (Bhikkhu Bodhi)
    - thanissaro (Thanissaro Bhikkhu / Ajahn Geoff)
    - ajahn-chah
    - ajahn-brahm
    - analayo
    - sujato
    - nanavira

    Args:
        teacher_slug: Author slug as used in the library
        limit: Maximum number of results
    """
    return _find_by_teacher(teacher_slug, limit=limit)


@mcp.tool()
def get_reading_path(topic: str, level: str = "beginner", limit: int = 10) -> list[dict]:
    """
    Generate a personalized reading/study path on a Buddhist topic.

    Combines semantic search with quality scoring to build a progressive path
    from foundational to advanced content.

    Args:
        topic: Topic to explore (e.g. "meditation", "dependent origination",
               "karuna compassion", "anatta no-self", "mindfulness in daily life")
        level: "beginner" (av + booklets preferred),
               "intermediate" (articles + monographs),
               "advanced" (papers + canon)
        limit: Number of items in the path (default 10)

    Returns:
        Ordered list of content items with path_order field
    """
    return _get_reading_path(topic=topic, level=level, limit=limit)


if __name__ == "__main__":
    mcp.run()
