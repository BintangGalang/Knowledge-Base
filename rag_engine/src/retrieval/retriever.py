"""
rag_engine/src/retrieval/retriever.py
Hybrid Search (Dense + Sparse BM25) + Cross-Encoder Re-ranking
"""
import os
from typing import List, Optional, Dict, Any
from dotenv import load_dotenv

load_dotenv()

from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import SparseVector


class MockNode:
    """Node sederhana yang meniru LlamaIndex Node untuk kompatibilitas."""
    def __init__(self, text: str, score: float, metadata: Dict[str, Any]):
        self.text = text
        self.score = score
        self.metadata = metadata

    def get_content(self) -> str:
        return self.text


class Retriever:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        model_name: str = "intfloat/multilingual-e5-large",
        collection_name: str = "shavira_undiksha_kb",
        db_path=None  # diabaikan, kompatibilitas lama
    ):
        print(f"[Retriever] Memuat embedding model: {model_name} ...")
        self.embed_model = SentenceTransformer(model_name)
        self.collection_name = collection_name

        print(f"[Retriever] Menghubungkan ke Qdrant {host}:{port} ...")
        self.client = QdrantClient(host=host, port=port)

        # Cek apakah koleksi mendukung sparse vector (hybrid search)
        self._supports_sparse = self._check_sparse_support()

        # Inisialisasi BM25 tokenizer untuk sparse vector
        self._bm25_tokenizer = None
        if self._supports_sparse:
            try:
                from transformers import AutoTokenizer
                self._bm25_tokenizer = AutoTokenizer.from_pretrained("Qdrant/bm25")
                print("[Retriever] Sparse BM25 tokenizer dimuat — Hybrid Search aktif.")
            except Exception as e:
                print(f"[Retriever] BM25 tokenizer tidak tersedia ({e}). Fallback ke dense-only.")
                self._supports_sparse = False

        # Inisialisasi Cross-Encoder Re-ranker
        self.reranker_model = None
        try:
            from sentence_transformers import CrossEncoder
            self.reranker_model = CrossEncoder(
                "cross-encoder/ms-marco-MiniLM-L-6-v2",
                max_length=512
            )
            print("[Retriever] Cross-Encoder Re-ranker dimuat.")
        except Exception as e:
            print(f"[Retriever] Re-ranker tidak tersedia ({e}). Fallback ke vector score.")

    def _check_sparse_support(self) -> bool:
        """Cek apakah koleksi Qdrant sudah dikonfigurasi untuk sparse vectors."""
        try:
            info = self.client.get_collection(self.collection_name)
            vectors_config = info.config.params.vectors
            if isinstance(vectors_config, dict):
                return "sparse" in vectors_config or any(
                    "sparse" in str(k).lower() for k in vectors_config.keys()
                )
            return False
        except Exception:
            return False

    def _build_sparse_vector(self, text: str) -> Optional[Dict]:
        """Bangun sparse (BM25) vector dari teks menggunakan tokenizer."""
        if not self._bm25_tokenizer:
            return None
        try:
            tokens = self._bm25_tokenizer(
                text, truncation=True, max_length=512,
                return_tensors=None, add_special_tokens=False
            )
            input_ids = tokens["input_ids"]
            # Hitung frekuensi token (TF sederhana)
            from collections import Counter
            tf = Counter(input_ids)
            indices = list(tf.keys())
            values = [float(v) for v in tf.values()]
            return {"indices": indices, "values": values}
        except Exception:
            return None

    def search(self, query_str: str, top_k: int = 5) -> List[MockNode]:
        """
        Hybrid Search: Dense (semantic) + Sparse (BM25 keyword) + Cross-Encoder Reranking.
        Fallback otomatis ke dense-only jika sparse tidak tersedia.
        """
        # 1. Encode query sebagai dense vector
        query_vector = self.embed_model.encode(
            f"query: {query_str}",
            normalize_embeddings=True
        ).tolist()

        # 2. Retrieve kandidat (ambil lebih banyak untuk re-ranking)
        candidate_limit = min(top_k * 5, 30)

        try:
            if self._supports_sparse:
                results = self._hybrid_search(query_str, query_vector, candidate_limit)
            else:
                results = self._dense_search(query_vector, candidate_limit)
        except Exception as e:
            print(f"[Retriever] Search error: {e}. Fallback ke dense search.")
            results = self._dense_search(query_vector, candidate_limit)

        if not results:
            return []

        # 3. Buat node list
        nodes = []
        for hit in results:
            payload = hit.payload or {}
            text = payload.get("text_full", payload.get("text", ""))
            score = getattr(hit, "score", 0.0)
            nodes.append(MockNode(text=text, score=float(score), metadata=payload))

        # 4. Re-ranking dengan Cross-Encoder
        return self._rerank(query_str, nodes, top_k)

    def _dense_search(self, query_vector: List[float], limit: int):
        """Dense-only semantic search."""
        return self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit
        ).points

    def _hybrid_search(self, query_str: str, query_vector: List[float], limit: int):
        """Hybrid dense + sparse search dengan Reciprocal Rank Fusion (RRF)."""
        sparse_data = self._build_sparse_vector(query_str)

        # Dense search
        dense_hits = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            limit=limit
        ).points

        if not sparse_data:
            return dense_hits

        # Sparse BM25 search
        try:
            sparse_hits = self.client.query_points(
                collection_name=self.collection_name,
                query=SparseVector(
                    indices=sparse_data["indices"],
                    values=sparse_data["values"]
                ),
                using="sparse",
                limit=limit
            ).points
        except Exception:
            return dense_hits

        # Reciprocal Rank Fusion (RRF)
        return self._rrf_fusion(dense_hits, sparse_hits, limit)

    def _rrf_fusion(self, dense_hits, sparse_hits, limit: int, k: int = 60):
        """Gabungkan hasil dense + sparse dengan RRF scoring."""
        scores: Dict[str, float] = {}
        docs: Dict[str, Any] = {}

        for rank, hit in enumerate(dense_hits):
            hit_id = str(hit.id)
            scores[hit_id] = scores.get(hit_id, 0.0) + 1.0 / (k + rank + 1)
            docs[hit_id] = hit

        for rank, hit in enumerate(sparse_hits):
            hit_id = str(hit.id)
            scores[hit_id] = scores.get(hit_id, 0.0) + 1.0 / (k + rank + 1)
            if hit_id not in docs:
                docs[hit_id] = hit

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

        fused = []
        for hit_id in sorted_ids[:limit]:
            hit = docs[hit_id]
            hit.score = scores[hit_id]
            fused.append(hit)
        return fused

    def _rerank(self, query_str: str, nodes: List[MockNode], top_k: int) -> List[MockNode]:
        """Re-rank nodes dengan Cross-Encoder, fallback ke vector score."""
        if not self.reranker_model or len(nodes) <= top_k:
            return nodes[:top_k]
        try:
            import numpy as np
            pairs = [[query_str, node.get_content()[:512]] for node in nodes]
            scores = self.reranker_model.predict(pairs, show_progress_bar=False)
            ranked_indices = np.argsort(scores)[::-1]
            reranked = [nodes[i] for i in ranked_indices[:top_k]]
            # Update score dari cross-encoder
            for i, node in enumerate(reranked):
                node.score = float(scores[ranked_indices[i]])
            return reranked
        except Exception as e:
            print(f"[Retriever] Re-rank error: {e}. Fallback ke original order.")
            return nodes[:top_k]

    def search_naive(self, query_str: str, top_k: int = 3) -> List[MockNode]:
        """Alias untuk kompatibilitas kode lama."""
        return self.search(query_str, top_k=top_k)