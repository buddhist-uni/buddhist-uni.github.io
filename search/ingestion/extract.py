"""
Text extraction from Buddhist University content files.
Builds a rich text representation for embedding, reusing existing pipeline code.
"""

import sys
import os
from pathlib import Path
from typing import Optional

# Allow importing from project root (website.py is in scripts/)
PROJECT_ROOT = Path(__file__).parent.parent.parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import frontmatter


def extract_text(file_path: str | Path, include_body: bool = True) -> str:
    """
    Build a rich text string from a content markdown file for embedding.

    Weighting strategy (inspired by tag_predictor.py):
    - Title: 3x (most discriminative)
    - Tags: 2x
    - Authors: 1x
    - Abstract/body: 1x (trimmed to 500 chars)

    Args:
        file_path: Path to markdown file with YAML frontmatter
        include_body: Whether to include the markdown body

    Returns:
        Concatenated text ready for embedding
    """
    path = Path(file_path)
    if not path.exists():
        return ""

    try:
        post = frontmatter.load(str(path))
    except Exception:
        return ""

    parts = []

    # Title (3x weight — repeat it)
    title = post.get("title", "")
    if title:
        clean_title = title.strip("*_").strip()
        parts.extend([clean_title] * 3)

    # Authors (convert slugs to readable names)
    authors = post.get("authors", [])
    if isinstance(authors, list) and authors:
        author_str = " ".join(
            a.replace("-", " ").replace("_", " ") for a in authors
            if isinstance(a, str)
        )
        if author_str.strip():
            parts.append(author_str)

    # Tags (2x weight — repeat)
    tags = post.get("tags", [])
    if isinstance(tags, list) and tags:
        tag_str = " ".join(t.replace("-", " ") for t in tags if isinstance(t, str))
        if tag_str.strip():
            parts.extend([tag_str] * 2)

    # Course
    course = post.get("course", "")
    if course:
        parts.append(course.replace("-", " "))

    # Abstract / body
    if include_body:
        body = post.content.strip() if post.content else ""
        if body:
            # Keep first 500 chars (abstract-level)
            body_preview = body[:500].strip()
            # Remove markdown syntax
            body_preview = body_preview.replace("#", "").replace("*", "").replace(">", "").strip()
            if body_preview:
                parts.append(body_preview)

    return " ".join(p for p in parts if p)


def build_payload(file_path: str | Path) -> dict:
    """
    Build the full Qdrant payload dict from a content file.
    Contains all metadata needed for filtering and display.
    """
    path = Path(file_path)
    post = frontmatter.load(str(path))
    meta = post.metadata

    # Determine category from path (e.g. _content/articles/ → articles)
    try:
        rel = path.relative_to(PROJECT_ROOT / "_content")
        category = rel.parts[0]
        slug = path.stem
    except ValueError:
        category = "unknown"
        slug = path.stem

    # Authors: list of strings
    authors = meta.get("authors", [])
    if not isinstance(authors, list):
        authors = [str(authors)] if authors else []
    authors = [str(a) for a in authors]

    # Tags: list of strings
    tags = meta.get("tags", [])
    if not isinstance(tags, list):
        tags = [str(tags)] if tags else []
    tags = [str(t) for t in tags]

    # Stars (quality score): compute from frontmatter
    # Mirrors the Jekyll plugin logic: 1-5 stars
    stars = meta.get("stars", None)
    if stars is None:
        # Simple heuristic: featured=5, has course=4, default=3
        if meta.get("featured"):
            stars = 5
        elif meta.get("course"):
            stars = 4
        else:
            stars = 3

    # Build canonical URL
    url = f"https://buddhistuniversity.net/content/{category}/{slug}"
    external_url = meta.get("external_url") or meta.get("source_url") or ""

    return {
        "slug": slug,
        "title": str(meta.get("title", slug)),
        "category": category,
        "tags": tags,
        "authors": authors,
        "course": str(meta.get("course", "")) or None,
        "year": int(meta.get("year", 0)) or None,
        "stars": int(stars),
        "url": url,
        "external_url": str(external_url) if external_url else None,
        "formats": meta.get("formats", []) if isinstance(meta.get("formats"), list) else [],
        "minutes": int(meta.get("minutes", 0)) or None,
        "pages": str(meta.get("pages", "")) or None,
    }


def get_all_content_files() -> list[Path]:
    """Return all markdown content files from _content/ directory."""
    content_dir = PROJECT_ROOT / "_content"
    if not content_dir.exists():
        raise FileNotFoundError(f"Content directory not found: {content_dir}")
    return sorted(content_dir.rglob("*.md"))


if __name__ == "__main__":
    # Quick test
    files = get_all_content_files()
    print(f"📚 {len(files)} fichiers de contenu trouvés")

    # Test on first file
    f = files[0]
    print(f"\n📄 Test sur: {f.name}")
    print("Text:", extract_text(f)[:200])
    print("Payload:", build_payload(f))
