"""
Tests unitaires — pipeline d'ingestion et recherche Qdrant.
Nécessite Qdrant en cours d'exécution avec la collection indexée.

Usage:
    PYTHONPATH=/path/to/buddhist-uni.github.io pytest search/tests/test_search.py -v
"""

import pytest
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent

# ──────────────────────────────────────────────
# Embedder
# ──────────────────────────────────────────────

class TestEmbedder:
    def test_encode_single_string(self):
        from search.ingestion.embedder import get_embedder
        e = get_embedder()
        vecs = e.encode("impermanence and suffering")
        assert vecs.shape == (1, 384)

    def test_encode_batch(self):
        from search.ingestion.embedder import get_embedder
        e = get_embedder()
        vecs = e.encode(["nibbana", "meditation", "pali grammar"])
        assert vecs.shape == (3, 384)

    def test_normalized_vectors(self):
        import numpy as np
        from search.ingestion.embedder import get_embedder
        e = get_embedder()
        vecs = e.encode(["anatta no-self"])
        norm = float(np.linalg.norm(vecs[0]))
        assert abs(norm - 1.0) < 1e-4, f"Vecteur non normalisé: norme={norm}"

    def test_encode_query_returns_list(self):
        from search.ingestion.embedder import get_embedder
        e = get_embedder()
        q = e.encode_query("karuna compassion")
        assert isinstance(q, list)
        assert len(q) == 384
        assert all(isinstance(x, float) for x in q)

    def test_singleton(self):
        from search.ingestion.embedder import get_embedder, Embedder
        e1 = get_embedder()
        e2 = get_embedder()
        assert e1 is e2


# ──────────────────────────────────────────────
# Extraction de texte
# ──────────────────────────────────────────────

class TestExtract:
    @pytest.fixture
    def sample_files(self):
        content_dir = PROJECT_ROOT / "_content"
        return list(content_dir.rglob("*.md"))[:20]

    def test_get_all_content_files(self):
        from search.ingestion.extract import get_all_content_files
        files = get_all_content_files()
        assert len(files) >= 4000, f"Attendu 4000+, obtenu {len(files)}"

    def test_extract_text_non_empty(self, sample_files):
        from search.ingestion.extract import extract_text
        non_empty = 0
        for f in sample_files:
            text = extract_text(f)
            if text.strip():
                non_empty += 1
        assert non_empty >= len(sample_files) * 0.8, "Trop de fichiers avec texte vide"

    def test_extract_text_contains_title(self, sample_files):
        from search.ingestion.extract import extract_text
        import frontmatter
        for f in sample_files[:5]:
            post = frontmatter.load(str(f))
            title = str(post.get("title", "")).strip("*_").strip()
            if not title:
                continue
            text = extract_text(f)
            # Le titre doit apparaître (potentiellement 3x)
            assert title[:20] in text, f"Titre absent du texte: {title[:30]}"
            break

    def test_build_payload_structure(self, sample_files):
        from search.ingestion.extract import build_payload
        payload = build_payload(sample_files[0])
        required = {"slug", "title", "category", "tags", "authors", "url", "stars"}
        for field in required:
            assert field in payload, f"Champ manquant: {field}"

    def test_payload_category_valid(self, sample_files):
        from search.ingestion.extract import build_payload
        valid_cats = {"articles", "av", "canon", "booklets", "essays",
                      "monographs", "papers", "excerpts", "reference"}
        for f in sample_files[:10]:
            p = build_payload(f)
            assert p["category"] in valid_cats, f"Catégorie invalide: {p['category']} ({f})"

    def test_payload_stars_range(self, sample_files):
        from search.ingestion.extract import build_payload
        for f in sample_files:
            p = build_payload(f)
            assert 1 <= p["stars"] <= 5, f"Stars hors range: {p['stars']}"


# ──────────────────────────────────────────────
# Qdrant — recherche sémantique
# ──────────────────────────────────────────────

@pytest.mark.integration
class TestQdrantSearch:
    """Ces tests nécessitent Qdrant UP avec la collection indexée."""

    def test_collection_has_documents(self):
        from search.ingestion.qdrant_setup import get_client, COLLECTION_NAME
        client = get_client()
        info = client.get_collection(COLLECTION_NAME)
        assert info.points_count >= 4000, f"Collection sous-indexée: {info.points_count} points"

    def test_search_returns_results(self):
        from search.server.tools import search_dharma
        results = search_dharma("impermanence suffering nibbana", limit=5)
        assert len(results) > 0
        assert len(results) <= 5

    def test_search_result_structure(self):
        from search.server.tools import search_dharma
        results = search_dharma("meditation mindfulness", limit=3)
        for r in results:
            assert "score" in r
            assert "title" in r
            assert "category" in r
            assert "url" in r
            assert 0.0 <= r["score"] <= 1.0

    def test_search_score_ordering(self):
        from search.server.tools import search_dharma
        results = search_dharma("pali grammar language", limit=8)
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True), "Résultats non triés par score"

    def test_search_filter_by_category(self):
        from search.server.tools import search_dharma
        results = search_dharma("anatta no-self", category="canon", limit=5)
        for r in results:
            assert r["category"] == "canon", f"Catégorie inattendue: {r['category']}"

    def test_search_filter_by_tag(self):
        from search.server.tools import search_dharma
        results = search_dharma("dependent origination", tags=["dependent-origination"], limit=5)
        for r in results:
            assert "dependent-origination" in r["tags"]

    def test_search_semantic_relevance(self):
        """Les résultats doivent être sémantiquement pertinents."""
        import unicodedata
        from search.server.tools import search_dharma

        def normalize(s: str) -> str:
            return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()

        results = search_dharma("Anattalakkhaṇa Sutta not-self characteristic", limit=5)
        titles = [normalize(r["title"]) for r in results]
        assert any(
            "anatt" in t or "not self" in t or "no-self" in t
            or r.get("category") == "canon"
            for t, r in zip(titles, results)
        ), f"Résultats non pertinents: {titles}"

    def test_search_empty_query_handled(self):
        from search.server.tools import search_dharma
        # Requête courte mais valide
        results = search_dharma("om", limit=3)
        assert isinstance(results, list)

    @pytest.mark.parametrize("query,expected_cat", [
        ("Majjhima Nikaya sutta discourse", "canon"),
        ("academic article research impermanence", "articles"),
    ])
    def test_search_category_bias(self, query, expected_cat):
        from search.server.tools import search_dharma
        results = search_dharma(query, limit=10)
        cats = [r["category"] for r in results]
        # Au moins un résultat de la catégorie attendue
        assert expected_cat in cats, f"Aucun résultat '{expected_cat}' pour '{query}'. Cats: {cats}"


# ──────────────────────────────────────────────
# Tools MCP
# ──────────────────────────────────────────────

@pytest.mark.integration
class TestMCPTools:

    def test_list_courses(self):
        from search.server.tools import list_courses
        courses = list_courses()
        assert len(courses) >= 10
        for c in courses:
            assert "id" in c
            assert "title" in c

    def test_get_course_mn(self):
        from search.server.tools import get_course
        result = get_course("mn")
        assert result is not None
        assert "Majjhima" in result["title"]
        assert result["content_count"] > 0
        assert len(result["content"]) > 0

    def test_get_course_not_found(self):
        from search.server.tools import get_course
        result = get_course("nonexistent-course-xyz")
        assert result is None

    def test_find_by_teacher_bodhi(self):
        from search.server.tools import find_by_teacher
        results = find_by_teacher("bodhi", limit=10)
        assert len(results) > 0
        for r in results:
            assert "title" in r
            assert "url" in r

    def test_find_by_teacher_sorted_by_stars(self):
        from search.server.tools import find_by_teacher
        results = find_by_teacher("bodhi", limit=10)
        stars = [r.get("stars", 0) for r in results]
        assert stars == sorted(stars, reverse=True), "Non trié par stars"

    def test_get_reading_path_beginner(self):
        from search.server.tools import get_reading_path
        path = get_reading_path("meditation mindfulness", level="beginner", limit=5)
        assert len(path) > 0
        assert len(path) <= 5
        for i, item in enumerate(path, 1):
            assert item["path_order"] == i
            assert item["level"] == "beginner"

    def test_get_reading_path_ordered(self):
        from search.server.tools import get_reading_path
        path = get_reading_path("dependent origination", level="intermediate", limit=8)
        orders = [item["path_order"] for item in path]
        assert orders == list(range(1, len(path) + 1))

    @pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced"])
    def test_get_reading_path_all_levels(self, level):
        from search.server.tools import get_reading_path
        path = get_reading_path("nibbana liberation", level=level, limit=5)
        assert isinstance(path, list)
        for item in path:
            assert item["level"] == level
