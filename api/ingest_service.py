import re
import uuid
import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import PointStruct

COLLECTION_NAME = "shavira_undiksha_kb"

def split_by_structure(text: str, doc_type: str) -> List[Dict[str, Any]]:
    """
    Split text adaptif berdasarkan struktur dokumen:
    - mou/perjanjian/sk/peraturan -> Pasal / Bab / Klausul
    - panduan/sop -> Seksi / Langkah
    - default -> Paragraf / Semantic Window (~400 kata)
    """
    chunks = []
    text = text.strip()
    
    if doc_type in ["mou", "peraturan", "sk"]:
        pattern = r'((?:BAB\s+[I|V|X]+|Pasal\s+\d+|Ayat\s+\d+|Klausul\s+\d+)[^\n]*)'
        sections = re.split(pattern, text, flags=re.IGNORECASE)
        
        current_header = "Umum"
        current_text = ""
        
        for part in sections:
            if not part:
                continue
            if re.match(r'^(BAB\s+[I|V|X]+|Pasal\s+\d+|Ayat\s+\d+|Klausul\s+\d+)', part.strip(), re.IGNORECASE):
                if current_text.strip():
                    chunks.append({"header": current_header, "text": current_text.strip()})
                current_header = part.strip()
                current_text = part
            else:
                current_text += part
                
        if current_text.strip():
            chunks.append({"header": current_header, "text": current_text.strip()})
            
    elif doc_type in ["panduan", "sop"]:
        lines = text.split("\n")
        current_header = "Pendahuluan"
        current_buffer = []
        
        for line in lines:
            if re.match(r'^(\d+\.|\#[^\#]|[A-Z\s]{4,}:)', line.strip()):
                if current_buffer:
                    chunks.append({"header": current_header, "text": "\n".join(current_buffer).strip()})
                    current_buffer = []
                current_header = line.strip()
            current_buffer.append(line)
            
        if current_buffer:
            chunks.append({"header": current_header, "text": "\n".join(current_buffer).strip()})
            
    # Fallback or default split into 400-word blocks if chunks were empty or too large
    if not chunks:
        words = text.split()
        chunk_size = 350
        overlap = 50
        step = chunk_size - overlap
        
        for i in range(0, len(words), step):
            block = " ".join(words[i:i+chunk_size])
            chunks.append({"header": f"Bagian {len(chunks)+1}", "text": block})
            
    return chunks


class IngestService:
    def __init__(self, qdrant_client: QdrantClient, embed_model: SentenceTransformer, collection_name: str = COLLECTION_NAME):
        self.client = qdrant_client
        self.embed_model = embed_model
        self.collection_name = collection_name

    def ingest_document(
        self,
        title: str,
        content: str,
        category: str = "lainnya",
        subcategory: str = "umum",
        document_type: str = "lainnya",
        source_url: str = "",
        source_unit: str = "Undiksha",
        status: str = "active",
        version: int = 1,
        topic_tags: List[str] = None,
        target_audience: List[str] = None
    ) -> Dict[str, Any]:
        if not topic_tags:
            topic_tags = ["undiksha", category]
        if not target_audience:
            target_audience = ["mahasiswa", "dosen", "staf"]

        doc_id = f"DOC-{uuid.uuid4().hex[:8].upper()}"
        content_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        crawled_at = datetime.now().isoformat()
        last_modified = datetime.now().isoformat()

        # ======================================================
        # DETEKSI DUPLIKASI: Cek apakah dokumen sudah ada di KB
        # ======================================================
        try:
            from qdrant_client.models import Filter, FieldCondition, MatchValue
            existing = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(must=[
                    FieldCondition(key="content_hash", match=MatchValue(value=content_hash))
                ]),
                limit=1,
                with_payload=True,
                with_vectors=False
            )
            if existing[0]:  # Ada dokumen dengan hash yang sama
                existing_doc_id = existing[0][0].payload.get("doc_id", "UNKNOWN")
                existing_title = existing[0][0].payload.get("title", title)
                print(f"[IngestService] DUPLIKAT terdeteksi! Dokumen '{title}' sudah ada sebagai '{existing_doc_id}'. Skip ingest.")
                return {
                    "status": "duplicate",
                    "doc_id": existing_doc_id,
                    "title": existing_title,
                    "category": existing[0][0].payload.get("category", category),
                    "document_type": existing[0][0].payload.get("document_type", document_type),
                    "chunks_ingested": 0,
                    "message": f"Dokumen duplikat ditemukan (doc_id: {existing_doc_id}). Ingest dibatalkan."
                }
        except Exception as dup_err:
            print(f"[IngestService] Gagal cek duplikasi: {dup_err}. Lanjutkan ingest.")


        raw_chunks = split_by_structure(content, document_type)
        
        points = []
        for idx, chunk_data in enumerate(raw_chunks):
            chunk_id = f"{doc_id}-C{idx+1:03d}"
            chunk_text = chunk_data["text"]
            header = chunk_data.get("header", "Bagian Umum")
            
            # Format text for embedding models (e5 format prefix 'passage: ')
            embedding_input = f"passage: {title}\n{header}\n{chunk_text}"
            vector = self.embed_model.encode(embedding_input, normalize_embeddings=True).tolist()
            
            payload = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "title": title,
                "category": category,
                "subcategory": subcategory,
                "document_type": document_type,
                "source_url": source_url,
                "source_unit": source_unit,
                "status": status,
                "version": version,
                "crawled_at": crawled_at,
                "last_modified": last_modified,
                "content_hash": content_hash,
                "topic_tags": topic_tags,
                "target_audience": target_audience,
                "section_header": header,
                "text": chunk_text,
                "text_full": chunk_text
            }
            
            points.append(PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload=payload
            ))
            
        if points:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )

        return {
            "status": "success",
            "doc_id": doc_id,
            "title": title,
            "category": category,
            "document_type": document_type,
            "chunks_ingested": len(points)
        }
