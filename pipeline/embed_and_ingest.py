from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import json, uuid
from tqdm import tqdm
MODEL_NAME = "intfloat/multilingual-e5-small"
COLLECTION_NAME = "shavira_undiksha_kb"
VECTOR_DIM = 384
def load_chunks(chunks_file: str) -> list[dict]:
    chunks = []
    with open(chunks_file, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks
def setup_collection(client: QdrantClient):
    """Buat collection Qdrant dengan konfigurasi optimal"""
    if client.collection_exists(COLLECTION_NAME):
        print(f"⚠️  Collection '{COLLECTION_NAME}' sudah ada. Menghapus untuk recreate...")
        client.delete_collection(collection_name=COLLECTION_NAME)
    
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE),
    )
    print(f"✅ Collection '{COLLECTION_NAME}' berhasil dibuat dengan dimensi {VECTOR_DIM}")
def embed_and_ingest(chunks: list[dict], client: QdrantClient, 
                     model: SentenceTransformer, batch_size: int = 32):
    """Embed dan ingest semua chunk"""
    
    total = len(chunks)
    ingested = 0
    
    for batch_start in tqdm(range(0, total, batch_size), desc="Embedding & Ingesting"):
        batch = chunks[batch_start:batch_start + batch_size]
        
        # Teks untuk embedding: gabung section_title + text untuk konteks lebih baik
        texts = []
        for c in batch:
            prefix = f"passage: "  # Prefix untuk multilingual-e5
            if c.get("section_title"):
                text = f"{prefix}{c['section_title']}. {c['text']}"
            else:
                text = f"{prefix}{c['title']}. {c['text']}"
            texts.append(text[:2000])  # Truncate agar tidak melebihi max length model
        
        embeddings = model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        
        points = []
        for chunk, embedding in zip(batch, embeddings):
            point = PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding.tolist(),
                payload={
                    # Teks (untuk display)
                    "chunk_id": chunk["chunk_id"],
                    "doc_id": chunk["doc_id"],
                    "text": chunk["text"][:1000],  # Simpan preview di payload
                    "text_full": chunk["text"],     # Simpan full text
                    "title": chunk["title"],
                    "section_title": chunk.get("section_title", ""),
                    "chunk_index": chunk["chunk_index"],
                    "total_chunks": chunk["total_chunks"],
                    
                    # Metadata untuk filtering
                    "category": chunk.get("category", ""),
                    "subcategory": chunk.get("subcategory", ""),
                    "document_type": chunk.get("document_type", ""),
                    "topic_tags": chunk.get("topic_tags", []),
                    "target_audience": chunk.get("target_audience", []),
                    "language": chunk.get("language", "id"),
                    "confidence_level": chunk.get("confidence_level", ""),
                    "related_units": chunk.get("related_units", []),
                    "is_time_sensitive": chunk.get("is_time_sensitive", False),
                    
                    # Sumber
                    "source_url": chunk.get("source_url", ""),
                    "target_site": chunk.get("target_site", ""),
                    "last_updated": chunk.get("last_updated", ""),
                    "doc_summary": chunk.get("doc_summary", ""),
                }
            )
            points.append(point)
        
        client.upsert(collection_name=COLLECTION_NAME, points=points)
        ingested += len(points)
    
    print(f"\n✅ Ingest selesai: {ingested:,} chunk tersimpan di Qdrant")
def test_queries(client: QdrantClient, model: SentenceTransformer):
    """Jalankan 10 query tes dan tampilkan hasilnya"""
    
    test_queries = [
        "Apa isi perjanjian kerjasama Undiksha dengan universitas luar negeri?",
        "Program pertukaran mahasiswa internasional",
        "Kerjasama bidang akuntansi dan manajemen",
        "Faculty of Economics collaboration agreement",
        "Student exchange program Bachelor Master Doctorate",
        "Memorandum of Agreement MoU Undiksha",
        "Kurikulum bersama joint curriculum development",
        "Visiting professor dan guest lecturer",
        "Penelitian bersama joint research publications",
        "Layanan komunitas community service program",
    ]
    
    print("\n" + "="*60)
    print("🔍 HASIL 10 QUERY TES")
    print("="*60)
    
    for i, query in enumerate(test_queries, 1):
        query_embedding = model.encode(
            f"query: {query}",
            normalize_embeddings=True,
        )
        
        results = client.search(
            collection_name=COLLECTION_NAME,
            query_vector=query_embedding.tolist(),
            limit=3,
        )
        
        print(f"\n[{i}] Query: \"{query}\"")
        for j, hit in enumerate(results, 1):
            print(f"     #{j} [{hit.score:.3f}] {hit.payload.get('title', 'N/A')[:60]}")
            # Replace newlines with spaces for printing
            preview = hit.payload.get('text', '')[:120].replace('\n', ' ')
            print(f"          {preview}...")
if __name__ == "__main__":
    print("Memuat model embedding (ini mungkin memakan waktu)...")
    model = SentenceTransformer(MODEL_NAME)
    print("Model dimuat. Menghubungkan ke Qdrant...")
    client = QdrantClient("localhost", port=6333)
    
    setup_collection(client)
    chunks = load_chunks("Data/chunks.jsonl")
    embed_and_ingest(chunks, client, model)
    test_queries(client, model)
