# 🎓 KBMS Shavira — Universitas Pendidikan Ganesha (Undiksha)

> **Knowledge Base Management System & RAG Assistant** untuk Dokumen Legal (JDIH) dan Dokumen Akademik Undiksha.

---

## 📁 Struktur Repositori

```text
shavira-kbms/
├── admin/                      # Web Admin Dashboard Frontend
│   └── index.html              # HTML5/CSS/JS Single-Page Dashboard (dengan Tab Web Crawler)
├── api/                        # FastAPI Backend Application
│   ├── schemas/                # Pydantic Schemas & Data Models
│   │   └── models.py
│   ├── analytics_service.py    # Analytics & Knowledge Gap Tracker
│   ├── ingest_service.py       # Adaptive Chunking & Qdrant Ingestion Service
│   └── main.py                 # FastAPI Application & Admin Dashboard Router
├── pipeline/                   # Pipeline Pemrosesan Data & Ingestion
│   ├── crawler_service.py      # [NEW] Web Crawler Service (Komponen 2 Diagram)
│   ├── audit_undiksha_jsonl.py
│   ├── clean_docs.py
│   ├── group_pages.py
│   ├── enrich_docs.py
│   ├── chunk_docs.py
│   ├── embed_and_ingest.py
│   └── stats.py
├── rag_engine/                 # Engine Hybrid Search & Generation LLM
│   └── src/
│       ├── retrieval/          # Qdrant Vector Search + Reranker
│       │   └── retriever.py
│       └── generation/         # OpenAI Generation LLM
│           └── generator.py
├── tests/                      # Automated Integration Test Suite
│   ├── test_phase9_api.py      # FastAPI, Dashboard & Crawler End-to-End Test
│   └── test_queries.py         # Batch Query Benchmark Test
├── data/                       # Directory Storage Data & Log Queries
│   └── raw_crawled/            # [NEW] Raw Web Data Store (Hasil Crawling)
├── temp/                       # Temporary Inspection Files
├── tech_stack.yaml             # Spesifikasi Arsitektur Sistem
├── requirements.txt            # Dependensi Python
└── README.md                   # Dokumentasi Utama
```

---

## 🚀 Panduan Menjalankan Sistem

### 1. Persiapan Environment (API Key)
Sebelum menjalankan sistem, Anda harus mengonfigurasi file `.env` di root direktori project.
Pastikan untuk memasukkan OpenAI API Key Anda:
```env
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxx
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin123
```

### 2. Jalankan FastAPI Backend & Web Admin Dashboard

Buka terminal dan jalankan uvicorn server pada **port 8000**:

```bash
cd d:\Magang\KBv2\shavira-kbms
# Aktifkan virtual environment jika menggunakan venv
.\rag_engine\venv\Scripts\python.exe -m uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 3. Akses Web Admin Dashboard

Setelah server berjalan, buka browser pada URL:
- 🌐 **Web Admin Dashboard**: [http://localhost:8000/admin](http://localhost:8000/admin) (atau [http://localhost:8000/](http://localhost:8000/))
- 📄 **API Interactive Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)

**Fitur Utama Dashboard:**
1. **Overview & Analytics**: Memantau statistik Knowledge Base, volume query, dan menemukan *Knowledge Gaps* (pertanyaan yang belum bisa dijawab oleh sistem).
2. **Web Crawler**: Melakukan scraping otomatis pada website Undiksha untuk diubah menjadi basis data pengetahuan.
3. **Knowledge Base**: Manajemen dokumen, tempat Anda bisa mengunggah PDF/DOCX baru atau menghapus dokumen lama.
4. **Query Test**: Menguji performa asisten RAG Shavira secara langsung melalui antarmuka chat.

---

## 🔌 API Endpoints Summary

| Endpoint | Method | Deskripsi |
|---|---|---|
| `/admin` & `/` | `GET` | Web Admin Dashboard UI (HTML5/Vanilla JS) |
| `/api/health` | `GET` | Status kesehatan server, Qdrant DB, & embedding model |
| `/api/chat` | `POST` | Hybrid retrieval + Reranking + LLM Generation |
| `/api/kb/documents` | `GET` | List ringkasan seluruh dokumen di Qdrant beserta metadata |
| `/api/kb/ingest` | `POST` | Adaptive chunking & embedding dokumen baru |
| `/api/kb/ingest-file` | `POST` | Ingest dokumen dari file (.pdf, .docx, .txt) |
| `/api/crawler/start` | `POST` | **[NEW]** Jalankan Web Crawler untuk domain Undiksha (Komponen 2) |
| `/api/crawler/status` | `GET` | **[NEW]** Ambil status real-time, statistik, & log web crawler |
| `/api/crawler/pages` | `GET` | **[NEW]** Daftar raw web pages hasil crawling |
| `/api/crawler/ingest-page/{id}`| `POST` | **[NEW]** Ingest manual raw page ke Qdrant Vector Store |
| `/api/analytics/gaps` | `GET` | Log pertanyaan unanswered / low confidence |

---

## 🧪 Menjalankan Pengujian Otomatis

Jalankan test script integrasi dari folder `tests`:

```bash
cd d:\Magang\KBv2\shavira-kbms
.\rag_engine\venv\Scripts\python.exe tests/test_phase9_api.py
```
