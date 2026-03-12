"""
Qdrant collection setup for Buddhist University content.
Run once to create the collection before ingestion.

Usage:
    python -m search.ingestion.qdrant_setup
"""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, OptimizersConfigDiff

COLLECTION_NAME = "buddhist_content"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimensions
QDRANT_URL = "http://localhost:6333"


def get_client() -> QdrantClient:
    return QdrantClient(url=QDRANT_URL)


def setup_collection(recreate: bool = False) -> None:
    client = get_client()

    existing = [c.name for c in client.get_collections().collections]

    if COLLECTION_NAME in existing:
        if recreate:
            print(f"🗑️  Suppression de la collection existante '{COLLECTION_NAME}'...")
            client.delete_collection(COLLECTION_NAME)
        else:
            print(f"✅ Collection '{COLLECTION_NAME}' déjà existante ({client.get_collection(COLLECTION_NAME).points_count} points)")
            return

    print(f"🔧 Création de la collection '{COLLECTION_NAME}'...")
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,
            distance=Distance.COSINE,
        ),
        optimizers_config=OptimizersConfigDiff(
            indexing_threshold=5000,  # build HNSW index after 5000 points
        ),
    )

    # Create payload indexes for fast filtering
    for field in ["category", "course", "year", "stars"]:
        client.create_payload_index(
            collection_name=COLLECTION_NAME,
            field_name=field,
            field_schema="keyword" if field in ("category", "course") else "integer",
        )

    # Tags is an array of strings
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="tags",
        field_schema="keyword",
    )

    info = client.get_collection(COLLECTION_NAME)
    print(f"✅ Collection créée: {COLLECTION_NAME}")
    print(f"   Dimensions: {VECTOR_SIZE}, Distance: COSINE")
    print(f"   Index sur: category, course, year, stars, tags")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Setup Qdrant collection for Buddhist University")
    parser.add_argument("--recreate", action="store_true", help="Supprimer et recréer la collection")
    args = parser.parse_args()

    try:
        setup_collection(recreate=args.recreate)
    except Exception as e:
        print(f"❌ Erreur de connexion à Qdrant ({QDRANT_URL}): {e}")
        print("   Assure-toi que Qdrant tourne: cd search && docker-compose up -d")
        raise SystemExit(1)
