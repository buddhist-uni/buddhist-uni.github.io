"""
Main ingestion pipeline: reads all content files, generates embeddings,
and upserts into Qdrant in batches.

Usage:
    cd /path/to/buddhist-uni.github.io
    python -m search.ingestion.ingest
    python -m search.ingestion.ingest --limit 100   # test mode
    python -m search.ingestion.ingest --recreate     # full re-index
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Iterator

from tqdm import tqdm
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

from .extract import extract_text, build_payload, get_all_content_files
from .embedder import get_embedder
from .qdrant_setup import COLLECTION_NAME, QDRANT_URL, setup_collection

BATCH_SIZE = 100


def slug_to_id(slug: str, category: str) -> int:
    """
    Convert slug + category to a stable integer ID for Qdrant.
    Uses MD5 and takes first 16 hex chars to avoid collisions.
    """
    key = f"{category}/{slug}"
    return int(hashlib.md5(key.encode()).hexdigest()[:16], 16) % (2**63)


def iter_batches(files: list[Path], batch_size: int) -> Iterator[list[Path]]:
    for i in range(0, len(files), batch_size):
        yield files[i : i + batch_size]


def ingest(
    limit: int | None = None,
    batch_size: int = BATCH_SIZE,
    recreate: bool = False,
    verbose: bool = False,
) -> int:
    """
    Run the full ingestion pipeline.

    Returns:
        Number of documents successfully indexed.
    """
    # Setup collection
    setup_collection(recreate=recreate)

    client = QdrantClient(url=QDRANT_URL)
    embedder = get_embedder()

    # Gather all content files
    all_files = get_all_content_files()
    if limit:
        all_files = all_files[:limit]

    print(f"\n📚 Ingestion de {len(all_files)} fichiers dans '{COLLECTION_NAME}'...")
    print(f"   Batch size: {batch_size} | Modèle: all-MiniLM-L6-v2")

    total_indexed = 0
    errors = []

    with tqdm(total=len(all_files), unit="doc", desc="Ingestion") as pbar:
        for batch_files in iter_batches(all_files, batch_size):
            texts = []
            payloads = []
            ids = []

            for file_path in batch_files:
                try:
                    text = extract_text(file_path)
                    payload = build_payload(file_path)

                    if not text.strip():
                        if verbose:
                            print(f"  ⚠️  Texte vide: {file_path.name}")
                        pbar.update(1)
                        continue

                    point_id = slug_to_id(payload["slug"], payload["category"])
                    texts.append(text)
                    payloads.append(payload)
                    ids.append(point_id)

                except Exception as e:
                    errors.append((str(file_path), str(e)))
                    if verbose:
                        print(f"  ❌ {file_path.name}: {e}")
                    pbar.update(1)

            if not texts:
                continue

            # Generate embeddings for this batch
            vectors = embedder.encode(texts, batch_size=batch_size)

            # Build Qdrant points
            points = [
                PointStruct(id=pid, vector=vec.tolist(), payload=payload)
                for pid, vec, payload in zip(ids, vectors, payloads)
            ]

            # Upsert (idempotent)
            client.upsert(collection_name=COLLECTION_NAME, points=points)
            total_indexed += len(points)
            pbar.update(len(batch_files))

    # Summary
    print(f"\n✅ Ingestion terminée!")
    print(f"   📊 {total_indexed} documents indexés")
    if errors:
        print(f"   ⚠️  {len(errors)} erreurs:")
        for path, err in errors[:5]:
            print(f"      {Path(path).name}: {err}")

    # Verify
    collection_info = client.get_collection(COLLECTION_NAME)
    print(f"   🔍 Qdrant contient: {collection_info.points_count} points")

    return total_indexed


def quick_test(query: str = "impermanence suffering nibbana") -> None:
    """Quick search test after ingestion."""
    from .embedder import get_embedder

    client = QdrantClient(url=QDRANT_URL)
    embedder = get_embedder()

    print(f'\n🔍 Test recherche: "{query}"')
    from qdrant_client.models import Query
    results = client.query_points(
        collection_name=COLLECTION_NAME,
        query=embedder.encode_query(query),
        limit=5,
    ).points
    for hit in results:
        p = hit.payload
        print(f"  [{hit.score:.3f}] {p.get('title','?')[:60]} ({p.get('category','?')})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Indexer le contenu Buddhist University dans Qdrant")
    parser.add_argument("--limit", type=int, help="Limiter à N fichiers (mode test)")
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    parser.add_argument("--recreate", action="store_true", help="Recréer la collection")
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--test-query", type=str, help="Lancer une recherche test après ingestion")
    args = parser.parse_args()

    n = ingest(
        limit=args.limit,
        batch_size=args.batch_size,
        recreate=args.recreate,
        verbose=args.verbose,
    )

    if args.test_query:
        quick_test(args.test_query)
    elif n > 0:
        quick_test()
