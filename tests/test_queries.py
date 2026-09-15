from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
MODEL_NAME = "intfloat/multilingual-e5-small"
COLLECTION_NAME = "shavira_undiksha_kb"
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
        
        # In newer qdrant-client versions, search is replaced by query_points
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=query_embedding.tolist(),
            limit=3,
        ).points
        
        print(f"\n[{i}] Query: \"{query}\"")
        for j, hit in enumerate(results, 1):
            print(f"     #{j} [{hit.score:.3f}] {hit.payload.get('title', 'N/A')[:60]}")
            # Replace newlines with spaces for printing
            preview = hit.payload.get('text', '')[:120].replace('\n', ' ')
            print(f"          {preview}...")
if __name__ == "__main__":
    print("Memuat model embedding untuk query...")
    model = SentenceTransformer(MODEL_NAME)
    print("Menghubungkan ke Qdrant...")
    client = QdrantClient("localhost", port=6333)
    
    test_queries(client, model)
