"""Pydantic models for the Buddhist University Search API."""

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    score: float
    title: str
    category: str
    tags: list[str] = []
    authors: list[str] = []
    course: str | None = None
    year: int | None = None
    stars: int | None = None
    url: str
    external_url: str | None = None
    minutes: int | None = None
    pages: str | None = None


class SearchResponse(BaseModel):
    query: str
    total: int
    results: list[SearchResult]


class CourseItem(BaseModel):
    title: str
    category: str
    tags: list[str] = []
    authors: list[str] = []
    year: int | None = None
    stars: int | None = None
    url: str
    minutes: int | None = None
    pages: str | None = None


class CourseDetail(BaseModel):
    id: str
    title: str
    subtitle: str = ""
    description: str = ""
    icon: str = ""
    next_courses: list[str] = []
    content_count: int
    content: list[CourseItem]


class CourseSummary(BaseModel):
    id: str
    title: str
    subtitle: str = ""
    icon: str = ""
    next_courses: list[str] = []


class ReadingPathItem(BaseModel):
    path_order: int
    level: str
    score: float
    title: str
    category: str
    tags: list[str] = []
    authors: list[str] = []
    stars: int | None = None
    url: str
    minutes: int | None = None
    pages: str | None = None
