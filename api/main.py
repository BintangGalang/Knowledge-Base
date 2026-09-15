import os
import sys
import time
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Form, BackgroundTasks, Depends, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from qdrant_client import QdrantClient

# Ensure workspace and rag_engine paths are in sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAG_ENGINE_DIR = os.path.join(BASE_DIR, "rag_engine")

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
if RAG_ENGINE_DIR not in sys.path:
    sys.path.insert(0, RAG_ENGINE_DIR)

from rag_engine.src.retrieval.retriever import Retriever
from rag_engine.src.generation.generator import Generator
from api.ingest_service import IngestService
from api.analytics_service import AnalyticsService
from api.config import get_settings
from api.auth import get_current_admin, create_access_token, verify_credentials
from pipeline.crawler_service import crawler_instance
from api.schemas.models import (
    ChatRequest, ChatResponse, SourceChunk, ChatMessage,
    DocumentIngestRequest, IngestResponse, HealthResponse,
    CrawlRequest, CrawlStatusResponse, CrawledPageItem
)

# Load konfigurasi dari .env
settings = get_settings()

app = FastAPI(
    title="KBMS Shavira Undiksha API & Admin Dashboard",
    description="Backend API dan Web Admin Dashboard untuk Sistem Manajemen Pengetahuan Undiksha",
    version="2.0.0"
)

# --- Auth Endpoint ---
@app.post("/api/auth/token", tags=["Auth"])
def login(username: str = Body(...), password: str = Body(...)):
    """Login admin untuk mendapatkan Bearer Token (valid 8 jam)"""
    if not verify_credentials(username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username atau password salah."
        )
    token = create_access_token()
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in_hours": 8,
        "message": f"Selamat datang, {username}! Token berlaku selama 8 jam."
    }

# Serve Web Admin Dashboard
@app.get("/admin", response_class=HTMLResponse)
@app.get("/", response_class=HTMLResponse)
def serve_admin_dashboard():
    admin_index_path = os.path.join(BASE_DIR, "admin", "index.html")
    if os.path.exists(admin_index_path):
        with open(admin_index_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Admin Dashboard index.html not found</h1>", status_code=404)

# Enable CORS for Streamlit admin dashboard & frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services (Lazy initialized on startup)
retriever: Optional[Retriever] = None
generator: Optional[Generator] = None
ingest_service: Optional[IngestService] = None
analytics_service: Optional[AnalyticsService] = None
qdrant_client: Optional[QdrantClient] = None

COLLECTION_NAME = settings.collection_name

@app.on_event("startup")
def startup_event():
    global retriever, generator, ingest_service, analytics_service, qdrant_client
    print("[Startup] Initializing KBMS Shavira Undiksha API Backend...")
    print(f"[Startup] Embed Model  : {settings.embed_model}")
    print(f"[Startup] LLM Model    : {settings.llm_model}")
    print(f"[Startup] Qdrant       : {settings.qdrant_host}:{settings.qdrant_port}")
    print(f"[Startup] Collection   : {settings.collection_name}")
    
    # Initialize Retriever & Generator
    retriever = Retriever(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        model_name=settings.embed_model,
        collection_name=COLLECTION_NAME
    )
    generator = Generator(model_name=settings.llm_model)
    
    # Initialize Qdrant Client & Services
    qdrant_client = retriever.client
    ingest_service = IngestService(
        qdrant_client=qdrant_client,
        embed_model=retriever.embed_model,
        collection_name=COLLECTION_NAME
    )
    analytics_service = AnalyticsService()
    print("[Startup] Services successfully initialized.")

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Status semua komponen (Qdrant, Embedding Model, LLM Backend)"""
    try:
        if not qdrant_client or not qdrant_client.collection_exists(COLLECTION_NAME):
            qdrant_status = "Disconnected or Collection Missing"
            total_vectors = 0
        else:
            info = qdrant_client.get_collection(COLLECTION_NAME)
            qdrant_status = "Connected"
            total_vectors = info.points_count or 0

        has_llm_key = bool(os.environ.get("OPENAI_API_KEY"))

        return HealthResponse(
            status="OK",
            qdrant_status=qdrant_status,
            collection_name=COLLECTION_NAME,
            total_vectors=total_vectors,
            embed_model=settings.embed_model,
            llm_configured=has_llm_key,
            timestamp=datetime.now().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")

@app.post("/api/chat", response_model=ChatResponse)
def chat_with_shavira(req: ChatRequest):
    """Query Shavira Assistant — Retrieval + Generation"""
    if not retriever or not generator or not analytics_service:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    start_time = time.time()
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    try:
        # 1. Retrieval
        nodes = retriever.search(query, top_k=req.top_k)
        
        # Format sources
        sources = []
        top_score = 0.0
        if nodes:
            top_score = float(nodes[0].score) if hasattr(nodes[0], 'score') else 0.0
            for node in nodes:
                meta = node.metadata if hasattr(node, 'metadata') else {}
                sources.append(SourceChunk(
                    chunk_id=meta.get("chunk_id"),
                    doc_id=meta.get("doc_id"),
                    title=meta.get("title", "Dokumen Undiksha"),
                    section_header=meta.get("section_header"),
                    category=meta.get("category"),
                    source_url=meta.get("source_url", ""),
                    source_unit=meta.get("source_unit", "Undiksha"),
                    text=node.get_content() if hasattr(node, 'get_content') else str(node),
                    score=round(float(node.score), 4) if hasattr(node, 'score') else 0.0
                ))
        
        # 2. Generation
        if not nodes:
            answer = "Maaf, informasi mengenai hal ini belum tersedia dalam basis pengetahuan Universitas Pendidikan Ganesha (Undiksha) yang saya miliki."
            is_gap = True
        else:
            # Konversi ChatMessage history dari request ke HistoryMessage generator
            from rag_engine.src.generation.generator import HistoryMessage
            history_msgs = [
                HistoryMessage(role=m.role, content=m.content)
                for m in (req.history or [])
            ]
            answer = generator.generate(query, nodes, history=history_msgs)
            
            # Deteksi low confidence
            is_gap = (
                "belum tersedia" in answer.lower()
                or "data tidak tersedia" in answer.lower()
                or top_score < 0.30
            )

        response_time = round(time.time() - start_time, 3)

        # 3. Log Analytics
        analytics_service.log_query(
            query=query,
            answer=answer,
            top_score=top_score,
            sources_count=len(sources),
            response_time_sec=response_time,
            is_gap=is_gap
        )

        return ChatResponse(
            query=query,
            answer=answer,
            sources=sources,
            confidence_score=round(top_score, 4),
            is_gap=is_gap,
            response_time_sec=response_time
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat generation failed: {str(e)}")

@app.get("/api/kb/documents", tags=["Knowledge Base"])
def list_documents(page: int = 1, limit: int = 20, category: Optional[str] = None, query: Optional[str] = None):
    """List dokumen di Knowledge Base dengan paginasi (page, limit) dan filter kategori/query."""
    if not qdrant_client:
        raise HTTPException(status_code=503, detail="Qdrant client unavailable")

    try:
        docs_map: Dict[str, Dict[str, Any]] = {}
        offset = None
        
        while True:
            scroll_res = qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                limit=200,
                offset=offset,
                with_payload=True,
                with_vectors=False
            )
            points, next_offset = scroll_res
            
            for point in points:
                payload = point.payload or {}
                doc_cat = payload.get("category", "lainnya")
                
                # Filter kategori jika diberikan
                if category and category != "ALL" and doc_cat != category:
                    continue
                
                title = payload.get("title", "Dokumen Tanpa Judul")
                doc_key = payload.get("doc_id", title)
                doc_type = payload.get("document_type", "lainnya")
                
                # Filter berdasarkan query pencarian (case-insensitive)
                if query:
                    q_lower = query.lower()
                    if (q_lower not in title.lower() and 
                        q_lower not in doc_key.lower() and 
                        q_lower not in doc_type.lower()):
                        continue
                
                if doc_key not in docs_map:
                    docs_map[doc_key] = {
                        "doc_id": payload.get("doc_id", doc_key),
                        "title": title,
                        "category": doc_cat,
                        "subcategory": payload.get("subcategory", "umum"),
                        "document_type": payload.get("document_type", "lainnya"),
                        "source_url": payload.get("source_url", ""),
                        "source_unit": payload.get("source_unit", "Undiksha"),
                        "status": payload.get("status", "active"),
                        "version": payload.get("version", 1),
                        "crawled_at": payload.get("crawled_at", ""),
                        "topic_tags": payload.get("topic_tags", []),
                        "target_audience": payload.get("target_audience", []),
                        "chunk_count": 0,
                        "sample_chunk": payload.get("text", "")[:150] + "..."
                    }
                docs_map[doc_key]["chunk_count"] += 1

            if next_offset is None or not points:
                break
            offset = next_offset

        doc_list = list(docs_map.values())
        total_documents = len(doc_list)
        total_chunks = sum(d["chunk_count"] for d in doc_list)
        
        # Paginasi
        limit = max(1, min(limit, 100))  # Batas 1-100
        page = max(1, page)
        total_pages = max(1, (total_documents + limit - 1) // limit)
        start_idx = (page - 1) * limit
        paginated = doc_list[start_idx: start_idx + limit]
        
        return {
            "total_documents": total_documents,
            "total_chunks": total_chunks,
            "page": page,
            "limit": limit,
            "total_pages": total_pages,
            "documents": paginated
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch documents: {str(e)}")


@app.get("/api/kb/documents/{doc_id:path}")
def get_document_details(doc_id: str):
    """Ambil detail dokumen beserta seluruh vector chunks miliknya"""
    if not qdrant_client:
        raise HTTPException(status_code=503, detail="Qdrant client unavailable")

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        
        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="doc_id",
                    match=MatchValue(value=doc_id)
                )
            ]
        )
        
        scroll_res = qdrant_client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=filter_condition,
            limit=500,
            with_payload=True,
            with_vectors=False
        )
        points, _ = scroll_res

        if not points:
            scroll_all, _ = qdrant_client.scroll(
                collection_name=COLLECTION_NAME,
                limit=1000,
                with_payload=True,
                with_vectors=False
            )
            points = [
                p for p in scroll_all
                if (p.payload or {}).get("doc_id") == doc_id or (p.payload or {}).get("title") == doc_id
            ]

        if not points:
            raise HTTPException(status_code=404, detail=f"Dokumen '{doc_id}' tidak ditemukan")

        first_payload = points[0].payload or {}
        doc_info = {
            "doc_id": first_payload.get("doc_id", doc_id),
            "title": first_payload.get("title", "Dokumen Tanpa Judul"),
            "category": first_payload.get("category", "lainnya"),
            "subcategory": first_payload.get("subcategory", "umum"),
            "document_type": first_payload.get("document_type", "lainnya"),
            "source_url": first_payload.get("source_url", ""),
            "source_unit": first_payload.get("source_unit", "Undiksha"),
            "status": first_payload.get("status", "active"),
            "version": first_payload.get("version", 1),
            "crawled_at": first_payload.get("crawled_at", ""),
            "topic_tags": first_payload.get("topic_tags", []),
            "target_audience": first_payload.get("target_audience", []),
            "total_chunks": len(points)
        }

        chunks = []
        for idx, point in enumerate(points):
            payload = point.payload or {}
            chunks.append({
                "chunk_id": payload.get("chunk_id", f"{doc_id}-C{idx+1:03d}"),
                "section_header": payload.get("section_header", f"Bagian {idx+1}"),
                "text": payload.get("text", payload.get("text_full", "")),
                "index": idx + 1
            })

        chunks.sort(key=lambda c: c["chunk_id"])

        return {
            "document": doc_info,
            "chunks": chunks
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch document details: {str(e)}")

@app.delete("/api/kb/documents/{doc_id:path}", tags=["Knowledge Base"])
def delete_document(doc_id: str, admin: str = Depends(get_current_admin)):
    """[🔒 Admin] Hapus dokumen dan seluruh vector chunks miliknya dari Qdrant"""
    if not qdrant_client:
        raise HTTPException(status_code=503, detail="Qdrant client unavailable")

    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue

        filter_condition = Filter(
            must=[
                FieldCondition(
                    key="doc_id",
                    match=MatchValue(value=doc_id)
                )
            ]
        )
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=filter_condition
        )

        filter_title = Filter(
            must=[
                FieldCondition(
                    key="title",
                    match=MatchValue(value=doc_id)
                )
            ]
        )
        qdrant_client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=filter_title
        )

        return {
            "status": "success",
            "message": f"Dokumen '{doc_id}' berhasil dihapus dari Knowledge Base",
            "doc_id": doc_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")

@app.post("/api/kb/ingest", response_model=IngestResponse, tags=["Knowledge Base"])
def ingest_document(req: DocumentIngestRequest, admin: str = Depends(get_current_admin)):
    """[🔒 Admin] Tambah dokumen baru ke KB dengan adaptive chunking & Qdrant embedding"""
    if not ingest_service:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")
    
    if not req.title.strip() or not req.content.strip():
        raise HTTPException(status_code=400, detail="Title and content are required")

    try:
        result = ingest_service.ingest_document(
            title=req.title,
            content=req.content,
            category=req.category,
            subcategory=req.subcategory,
            document_type=req.document_type,
            source_url=req.source_url or "",
            source_unit=req.source_unit or "Undiksha",
            status=req.status or "active",
            version=req.version or 1,
            topic_tags=req.topic_tags,
            target_audience=req.target_audience
        )
        return IngestResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@app.post("/api/kb/ingest-file", response_model=IngestResponse, tags=["Knowledge Base"])
async def ingest_document_file(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: str = Form("lainnya"),
    subcategory: str = Form("umum"),
    document_type: str = Form("lainnya"),
    source_unit: str = Form("Undiksha"),
    topic_tags: Optional[str] = Form(None),
    admin: str = Depends(get_current_admin)
):
    """[🔒 Admin] Tambah dokumen baru dari unggahan file (.pdf, .docx, .doc, .txt, .md)"""
    if not ingest_service:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    try:
        from api.document_parser import extract_text_from_file

        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="File unggahan kosong")

        extracted_text = extract_text_from_file(file.filename, file_bytes)
        final_title = title.strip() if title and title.strip() else os.path.splitext(file.filename)[0]
        tags_list = [t.strip() for t in topic_tags.split(",") if t.strip()] if topic_tags else ["undiksha", category]

        result = ingest_service.ingest_document(
            title=final_title,
            content=extracted_text,
            category=category,
            subcategory=subcategory,
            document_type=document_type,
            source_url=file.filename,
            source_unit=source_unit,
            status="active",
            version=1,
            topic_tags=tags_list,
            target_audience=["mahasiswa", "dosen", "staf"]
        )
        return IngestResponse(**result)
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File ingestion failed: {str(e)}")

# ==========================================
# CRAWLER API ENDPOINTS (Komponen 2 Diagram)
# ==========================================

async def _run_crawler_background(seed_url: str, allowed_domain: Optional[str], max_pages: int, auto_ingest: bool):
    await crawler_instance.crawl_site(
        seed_url=seed_url,
        allowed_domain=allowed_domain,
        max_pages=max_pages,
        auto_ingest=auto_ingest,
        ingest_service=ingest_service
    )

@app.post("/api/crawler/start", tags=["Crawler"])
def start_crawler(req: CrawlRequest, background_tasks: BackgroundTasks, admin: str = Depends(get_current_admin)):
    """[🔒 Admin] Mulai proses Web Crawler untuk domain Undiksha di background"""
    if crawler_instance.is_running:
        raise HTTPException(status_code=400, detail="Crawler sedang berjalan. Tunggu hingga selesai.")

    background_tasks.add_task(
        _run_crawler_background,
        seed_url=req.seed_url,
        allowed_domain=req.allowed_domain,
        max_pages=req.max_pages,
        auto_ingest=req.auto_ingest
    )

    return {
        "status": "started",
        "message": f"Web crawler berhasil dimulai untuk {req.seed_url}",
        "max_pages": req.max_pages,
        "auto_ingest": req.auto_ingest
    }

@app.get("/api/crawler/status", tags=["Crawler"])
def get_crawler_status():
    """Ambil status & log real-time proses web crawler"""
    return crawler_instance.get_status()

@app.delete("/api/crawler/history", tags=["Crawler"])
def clear_crawler_history(admin: str = Depends(get_current_admin)):
    """[🔒 Admin] Hapus persistent URL history agar semua halaman bisa di-crawl ulang"""
    crawler_instance.clear_history()
    return {"status": "success", "message": "Crawler URL history berhasil dihapus."}

@app.get("/api/crawler/pages")
def get_crawled_pages():
    """Daftar raw web pages hasil crawling"""
    pages = crawler_instance.list_crawled_pages()
    return {
        "total_crawled": len(pages),
        "pages": pages
    }

@app.get("/api/crawler/pages/{page_id}")
def get_crawled_page_detail(page_id: str):
    """Detail teks & metadata dari satu raw crawled page"""
    doc = crawler_instance.get_crawled_page_detail(page_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Halaman crawl '{page_id}' tidak ditemukan")
    return doc

@app.post("/api/crawler/ingest-page/{page_id}", tags=["Crawler"])
def ingest_crawled_page(page_id: str, admin: str = Depends(get_current_admin)):
    """[🔒 Admin] Ingest raw page hasil crawl ke Qdrant Vector Store secara manual"""
    if not ingest_service:
        raise HTTPException(status_code=503, detail="Ingest service not initialized")

    doc = crawler_instance.get_crawled_page_detail(page_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Halaman crawl '{page_id}' tidak ditemukan")

    try:
        res = ingest_service.ingest_document(
            title=doc.get("title", "Halaman Web Undiksha"),
            content=doc.get("text", ""),
            category=doc.get("category", "lainnya"),
            subcategory=doc.get("source_unit", "Web Undiksha"),
            document_type=doc.get("document_type", "web_page"),
            source_url=doc.get("source_url", ""),
            source_unit=doc.get("source_unit", "Web Undiksha"),
            status="active",
            version=1,
            topic_tags=["crawled", doc.get("category", "lainnya"), "undiksha"],
            target_audience=["mahasiswa", "dosen", "staf", "umum"]
        )
        return IngestResponse(**res)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Manual ingest failed: {str(e)}")

@app.get("/api/analytics/gaps", tags=["Analytics"])
def get_analytics_gaps():
    """Dapatkan daftar pertanyaan tidak terjawab (knowledge gaps)"""
    if not analytics_service:
        raise HTTPException(status_code=503, detail="Analytics service not initialized")
    return analytics_service.get_gaps()

@app.get("/api/analytics/overview", tags=["Analytics"])
def get_analytics_overview():
    """Dapatkan data statistik ringkasan dashboard"""
    if not analytics_service or not qdrant_client:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    try:
        info = qdrant_client.get_collection(COLLECTION_NAME)
        total_chunks = info.points_count or 0
    except Exception:
        total_chunks = 0

    return analytics_service.get_overview_stats(total_docs=0, total_chunks=total_chunks)

@app.get("/api/analytics/trend", tags=["Analytics"])
def get_analytics_trend(days: int = 7):
    """Tren jumlah query per hari (untuk grafik dashboard, default 7 hari)"""
    if not analytics_service:
        raise HTTPException(status_code=503, detail="Analytics service not initialized")
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="Parameter 'days' harus antara 1-90")
    return {"trend": analytics_service.get_query_trend(days=days)}

@app.get("/api/analytics/top-queries", tags=["Analytics"])
def get_top_queries(n: int = 10):
    """Top N pertanyaan yang paling sering diajukan"""
    if not analytics_service:
        raise HTTPException(status_code=503, detail="Analytics service not initialized")
    return {"top_queries": analytics_service.get_top_queries(n=n)}
