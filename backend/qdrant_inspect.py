"""Quick script to inspect Qdrant data."""
import asyncio
from qdrant_client import QdrantClient

client = QdrantClient(host="host.docker.internal", port=6333)

# List collections
collections = client.get_collections()
print("=" * 60)
print("QDRANT COLLECTIONS")
print("=" * 60)
for c in collections.collections:
    info = client.get_collection(c.name)
    print(f"\nCollection: {c.name}")
    print(f"  Points Count: {info.points_count}")
    print(f"  Vector Size: {info.config.params.vectors.size}")
    print(f"  Distance: {info.config.params.vectors.distance}")
    
    # Scroll through points
    points, _ = client.scroll(
        collection_name=c.name,
        limit=10,
        with_payload=True,
        with_vectors=False,
    )
    
    print(f"\n  --- Stored Data Points ({len(points)} shown) ---")
    for i, point in enumerate(points):
        payload = point.payload
        print(f"\n  Point {i+1}:")
        print(f"    ID: {point.id}")
        print(f"    user_id: {payload.get('user_id', 'N/A')}")
        print(f"    document_id: {payload.get('document_id', 'N/A')}")
        print(f"    source_filename: {payload.get('source_filename', 'N/A')}")
        print(f"    chunk_index: {payload.get('chunk_index', 'N/A')}")
        print(f"    page_number: {payload.get('page_number', 'N/A')}")
        text = payload.get('text', '')
        print(f"    text (child chunk): {text[:200]}...")
        parent = payload.get('parent_text', '')
        print(f"    parent_text (first 200 chars): {parent[:200]}...")

print("\n" + "=" * 60)
print("INSPECTION COMPLETE")
print("=" * 60)
