from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ChatMessage(BaseModel):
    """Satu pesan dalam riwayat percakapan multi-turn."""
    role: str = Field(..., description="'user' atau 'assistant'")
    content: str = Field(..., description="Isi pesan")

class ChatRequest(BaseModel):
    query: str = Field(..., description="Pertanyaan untuk Shavira Undiksha", example="Apa saja jalur penerimaan mahasiswa baru di Undiksha?")
    top_k: Optional[int] = Field(5, description="Jumlah chunk yang diretrieve", example=5)
    history: Optional[List[ChatMessage]] = Field(default=[], description="Riwayat percakapan sebelumnya (max 6 pesan)")

class SourceChunk(BaseModel):
    chunk_id: Optional[str] = None
    doc_id: Optional[str] = None
    title: str
    section_header: Optional[str] = None
    category: Optional[str] = None
    source_url: Optional[str] = None
    source_unit: Optional[str] = None
    text: str
    score: float

class ChatResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceChunk]
    confidence_score: float
    is_gap: bool
    response_time_sec: float

class DocumentIngestRequest(BaseModel):
    title: str = Field(..., description="Judul Dokumen", example="SK Rektor No 123/UN48/HK/2024")
    content: str = Field(..., description="Isi/Teks lengkap dokumen")
    category: Optional[str] = Field("lainnya", description="Kategori utama")
    subcategory: Optional[str] = Field("umum", description="Subkategori spesifik")
    document_type: Optional[str] = Field("lainnya", description="Jenis dokumen (mou, sk, peraturan, panduan, silabus, dll)")
    source_url: Optional[str] = Field("", description="URL sumber asal dokumen")
    source_unit: Optional[str] = Field("Undiksha", description="Unit penerbit / pemilik dokumen")
    status: Optional[str] = Field("active", description="Status dokumen (active/archived)")
    version: Optional[int] = Field(1, description="Versi dokumen")
    topic_tags: Optional[List[str]] = Field(default_factory=list, description="Tag topik dokumen")
    target_audience: Optional[List[str]] = Field(default_factory=list, description="Target audiens")

class IngestResponse(BaseModel):
    status: str
    doc_id: str
    title: str
    category: str
    document_type: str
    chunks_ingested: int

class HealthResponse(BaseModel):
    status: str
    qdrant_status: str
    collection_name: str
    total_vectors: int
    embed_model: str
    llm_configured: bool
    timestamp: str

# Crawler Models
class CrawlRequest(BaseModel):
    seed_url: str = Field("https://undiksha.ac.id", description="URL utama target crawling")
    allowed_domain: Optional[str] = Field("undiksha.ac.id", description="Domain filter untuk pembatasan crawl")
    max_pages: Optional[int] = Field(15, description="Batas maksimal halaman yang diambil", ge=1, le=100)
    auto_ingest: Optional[bool] = Field(True, description="Otomatis ingest hasil crawl ke Qdrant KB Store")

class CrawlStatusResponse(BaseModel):
    is_running: bool
    current_seed: str
    allowed_domain: str
    max_pages: int
    pages_crawled: int
    duration_sec: float
    auto_ingest: bool
    logs: List[str]
    total_logs_count: int

class CrawledPageItem(BaseModel):
    page_id: str
    title: str
    source_url: str
    source_unit: str
    category: str
    document_type: str
    crawled_at: str
    word_count: int
    status: str
    version: int
