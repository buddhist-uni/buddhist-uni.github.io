# Buddhist University — Moteur de recherche vectoriel + MCP Server

Recherche sémantique dans **4 494 ressources bouddhistes** (textes canoniques, articles académiques, AV, cours) via une base vectorielle [Qdrant](https://qdrant.tech/) et le modèle d'embeddings `all-MiniLM-L6-v2`.

Expose les résultats via une **API REST FastAPI** et un **serveur MCP** branché directement sur Claude.

---

## Architecture

```
_content/         ← 4494 fichiers markdown (source de vérité Jekyll)
search/
├── ingestion/    ← Pipeline: extraction → embeddings → Qdrant
│   ├── extract.py        réutilise website.py + frontmatter
│   ├── embedder.py       sentence-transformers/all-MiniLM-L6-v2
│   └── ingest.py         pipeline principal (batch 100, ~25s)
├── api/          ← FastAPI REST (port 8001)
│   ├── main.py           app + CORS + routes
│   ├── search.py         GET /search, GET /reading-path
│   ├── courses.py        GET /courses, GET /courses/{id}, GET /teachers/{slug}
│   └── models.py         Pydantic models
├── server/       ← MCP Server (5 tools pour Claude)
│   ├── mcp_server.py     FastMCP + déclaration des tools
│   └── tools.py          fonctions Qdrant partagées API + MCP
├── tests/        ← 56 tests (unit + integration)
│   ├── test_search.py
│   ├── test_api.py
│   └── pytest.ini
├── docker-compose.yml    Qdrant
├── requirements.txt
└── README.md
.mcp.json         ← Config MCP pour Claude Code (racine du projet)
```

---

## Setup (première fois)

### 1. Créer l'environnement Python

```bash
cd buddhist-uni.github.io
uv venv search/.venv --python 3.12
uv pip install --python search/.venv/bin/python -r search/requirements.txt
```

### 2. Démarrer Qdrant

```bash
cd search && docker-compose up -d
# Vérifier : curl localhost:6333/healthz
# Dashboard : http://localhost:6333/dashboard
```

### 3. Indexer les 4494 documents (~25 secondes)

```bash
PYTHONPATH=$(pwd) search/.venv/bin/python -m search.ingestion.ingest
```

Options :
```bash
# Test sur 100 fichiers
--limit 100

# Réindexer entièrement
--recreate

# Requête de test après ingestion
--test-query "impermanence nibbana"
```

---

## Utilisation

### API REST (FastAPI)

```bash
PYTHONPATH=$(pwd) search/.venv/bin/uvicorn search.api.main:app --port 8001 --reload
```

**Docs interactives** → http://localhost:8001/docs

| Endpoint | Exemple |
|---|---|
| `GET /search` | `/search?q=meditation+breath&limit=8` |
| `GET /search` (filtres) | `/search?q=nibbana&category=canon&min_stars=4` |
| `GET /search` (tags) | `/search?q=compassion&tags=metta&tags=karuna` |
| `GET /reading-path` | `/reading-path?topic=anatta&level=beginner` |
| `GET /courses` | `/courses` |
| `GET /courses/{id}` | `/courses/mn` · `/courses/pali-primer` |
| `GET /teachers/{slug}` | `/teachers/bodhi` · `/teachers/thanissaro` |
| `GET /health` | État de Qdrant |

**Paramètres `/search`** :
- `q` — requête en langage naturel (obligatoire)
- `category` — `articles` `canon` `av` `booklets` `essays` `monographs` `papers` `excerpts` `reference`
- `tags` — tags multiples (ex: `&tags=metta&tags=meditation`)
- `course` — slug de cours (ex: `mn`, `abhidhamma`)
- `min_stars` — qualité minimale 1–5
- `limit` — 1–20 (défaut 8)

**Paramètres `/reading-path`** :
- `topic` — sujet à explorer
- `level` — `beginner` · `intermediate` · `advanced`
- `limit` — 1–20 (défaut 10)

### MCP Server (Claude Code)

Le fichier `.mcp.json` est déjà configuré à la racine du projet.
**Ouvre un nouveau Claude Code dans ce dossier** — les 5 tools sont disponibles automatiquement.

| Tool MCP | Description |
|---|---|
| `search_dharma(query, tags?, category?, limit?)` | Recherche sémantique |
| `get_course(course_id)` | Curriculum complet d'un cours |
| `list_courses()` | Liste des 16 cours structurés |
| `find_by_teacher(teacher_slug)` | Ressources par enseignant |
| `get_reading_path(topic, level, limit)` | Parcours de lecture guidé |

**Cours disponibles** : `an` `buddha` `buddhism` `chinese-primer` `ebts` `ethics` `form` `function` `imagery` `mn` `nibbana` `nibbana-mind-stilled` `pali-new-course` `pali-primer` `philosophy` `tranquility-and-insight`

**Enseignants** (exemples) : `bodhi` `thanissaro` `ajahn-chah` `ajahn-brahm` `analayo` `sujato` `nanavira`

---

## Tests

```bash
# Tests unitaires (pas besoin de Qdrant)
PYTHONPATH=$(pwd) search/.venv/bin/pytest search/tests/ -m "not integration" -v

# Tests complets (Qdrant requis)
PYTHONPATH=$(pwd) search/.venv/bin/pytest search/tests/ -v

# Résultat attendu : 56 passed
```

---

## Réindexation

Si tu ajoutes du nouveau contenu dans `_content/` :

```bash
# Réindexation incrémentale (upsert, safe)
PYTHONPATH=$(pwd) search/.venv/bin/python -m search.ingestion.ingest

# Réindexation complète (repart de zéro)
PYTHONPATH=$(pwd) search/.venv/bin/python -m search.ingestion.ingest --recreate
```

---

## Stack technique

| Composant | Technologie | Raison |
|---|---|---|
| Vector DB | **Qdrant** (Docker) | Filtres metadata natifs, HNSW, open-source |
| Embeddings | **all-MiniLM-L6-v2** | 384 dims, local, rapide (~500 docs/s), gratuit |
| API | **FastAPI** + uvicorn | Async, autodoc OpenAPI, Pydantic v2 |
| MCP | **FastMCP** (Anthropic SDK) | Stdio transport, compatible Claude Code |
| Extraction | **python-frontmatter** | Réutilise le pipeline Jekyll existant |
