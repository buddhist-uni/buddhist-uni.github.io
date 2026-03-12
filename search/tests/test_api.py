"""
Tests d'intégration FastAPI — tous les endpoints.

Usage:
    PYTHONPATH=/path/to/buddhist-uni.github.io pytest search/tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from search.api.main import app

client = TestClient(app)


class TestHealth:
    def test_root(self):
        r = client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert data["name"] == "Buddhist University Search API"
        assert "endpoints" in data

    def test_health_ok(self):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"
        assert data["indexed_documents"] >= 4000


@pytest.mark.integration
class TestSearchEndpoint:
    def test_basic_search(self):
        r = client.get("/search?q=meditation+mindfulness")
        assert r.status_code == 200
        data = r.json()
        assert data["query"] == "meditation mindfulness"
        assert data["total"] > 0
        assert len(data["results"]) > 0

    def test_search_with_limit(self):
        r = client.get("/search?q=nibbana&limit=3")
        assert r.status_code == 200
        data = r.json()
        assert len(data["results"]) <= 3

    def test_search_limit_max(self):
        r = client.get("/search?q=nibbana&limit=25")
        assert r.status_code == 422  # limit max=20

    def test_search_result_fields(self):
        r = client.get("/search?q=impermanence")
        data = r.json()
        result = data["results"][0]
        assert "score" in result
        assert "title" in result
        assert "category" in result
        assert "url" in result
        assert "tags" in result

    def test_search_filter_category(self):
        r = client.get("/search?q=anatta&category=canon")
        assert r.status_code == 200
        data = r.json()
        for result in data["results"]:
            assert result["category"] == "canon"

    def test_search_filter_multiple_tags(self):
        r = client.get("/search?q=compassion&tags=metta&tags=meditation")
        assert r.status_code == 200
        assert r.json()["total"] >= 0  # peut être 0 si pas de match exact

    def test_search_missing_query(self):
        r = client.get("/search")
        assert r.status_code == 422

    def test_search_short_query(self):
        r = client.get("/search?q=a")
        assert r.status_code == 422  # min_length=2

    def test_search_scores_ordered(self):
        r = client.get("/search?q=pali+grammar&limit=8")
        data = r.json()
        scores = [res["score"] for res in data["results"]]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.integration
class TestReadingPath:
    def test_basic_path(self):
        r = client.get("/reading-path?topic=karuna+compassion")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0
        assert data[0]["path_order"] == 1

    def test_path_ordered(self):
        r = client.get("/reading-path?topic=meditation&level=beginner&limit=8")
        data = r.json()
        orders = [item["path_order"] for item in data]
        assert orders == list(range(1, len(data) + 1))

    def test_path_level_field(self):
        for level in ["beginner", "intermediate", "advanced"]:
            r = client.get(f"/reading-path?topic=nibbana&level={level}")
            assert r.status_code == 200
            for item in r.json():
                assert item["level"] == level

    def test_path_invalid_level(self):
        r = client.get("/reading-path?topic=nibbana&level=expert")
        assert r.status_code == 422

    def test_path_missing_topic(self):
        r = client.get("/reading-path")
        assert r.status_code == 422


@pytest.mark.integration
class TestCoursesEndpoint:
    def test_list_courses(self):
        r = client.get("/courses")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 10
        ids = [c["id"] for c in data]
        assert "mn" in ids
        assert "pali-primer" in ids

    def test_list_courses_fields(self):
        r = client.get("/courses")
        for course in r.json():
            assert "id" in course
            assert "title" in course

    def test_get_course_mn(self):
        r = client.get("/courses/mn")
        assert r.status_code == 200
        data = r.json()
        assert "Majjhima" in data["title"]
        assert data["content_count"] > 0
        assert len(data["content"]) > 0

    def test_get_course_pali(self):
        r = client.get("/courses/pali-primer")
        assert r.status_code == 200
        data = r.json()
        assert "Pāl" in data["title"] or "Pali" in data["title"]

    def test_get_course_not_found(self):
        r = client.get("/courses/nonexistent-xyz")
        assert r.status_code == 404

    def test_course_content_fields(self):
        r = client.get("/courses/mn")
        data = r.json()
        item = data["content"][0]
        assert "title" in item
        assert "category" in item
        assert "url" in item


@pytest.mark.integration
class TestTeachersEndpoint:
    def test_get_teacher_bodhi(self):
        r = client.get("/teachers/bodhi")
        assert r.status_code == 200
        data = r.json()
        assert len(data) > 0

    def test_get_teacher_not_found(self):
        r = client.get("/teachers/nobody-xyz-unknown")
        assert r.status_code == 404

    def test_teacher_result_fields(self):
        r = client.get("/teachers/bodhi?limit=3")
        for item in r.json():
            assert "title" in item
            assert "url" in item
            assert "category" in item
