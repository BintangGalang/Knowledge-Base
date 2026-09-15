# Virtual Campus Assistant
## 🌟 Fitur Utama

- **RAG Berpresisi Tinggi**: Menjawab pertanyaan pengguna strictly berbasis konteks dokumen internal untuk mencegah halusinasi.
- **Sitasi & Referensi Otomatis**: Setiap jawaban menyertakan bagian **"REFERENSI DOKUMEN"** lengkap dengan nama file sumber dan nomor halaman (`page_label`).
- **Token Text Splitter Chunking**: Menggunakan `TokenTextSplitter` dari LlamaIndex (chunk size: 512 tokens, overlap: 50 tokens) untuk pemotongan teks yang efisien dan konsisten.
- **Multilingual Embeddings**: Menggunakan model `intfloat/multilingual-e5-large` dari HuggingFace yang sangat optimal untuk teks bahasa Indonesia & Inggris.
- **Pipeline Ingestion Otomatis & Incremental**: Memproses dokumen dari `data/raw/` dengan sistem manifest (`ingestion_manifest.json`) sehingga hanya memproses file baru atau file yang dimodifikasi (MD5 hash checking).
- **Dua Pilihan Antarmuka**:
  - **Web UI Dashboard**: Antarmuka interaktif dan modern berbasis **Streamlit**.
  - **CLI (Terminal)**: Mode baris perintah cepat untuk pengujian langsung.

---

## 🛠️ Tech Stack

| Komponen | Teknologi / Model |
| :--- | :--- |
| **Framework RAG** | [LlamaIndex](https://www.llamaindex.ai/) |
| **LLM (Generator)** | OpenAI `gpt-4o-mini` |
| **Embedding Model** | `intfloat/multilingual-e5-large` (HuggingFace) |
| **Chunking Strategy** | `TokenTextSplitter` (512 tokens, 50 overlap) |
| **Vector Database** | FAISS (`faiss-cpu`) |
| **PDF Parser** | PyMuPDF / PyMuPDF4LLM |
| **Web Interface** | [Streamlit](https://streamlit.io/) |

---

## 📂 Struktur Proyek

```text
RAG-GPT/
├── app/                        # Aplikasi CLI interaktif
│   └── cli.py                  # Logika antarmuka terminal
├── data/                       # Penyimpanan data pemrosesan
│   ├── raw/                    # Tempat menaruh file PDF asli
│   ├── cleaned/                # Hasil ekstraksi teks bersih (MD)
│   └── chunk/                  # Hasil pemotongan teks (JSON)
├── src/                        # Modul inti RAG
│   ├── ingestion/              # Pipeline pemrosesan dokumen
│   │   ├── loader.py           # Ekstraksi PDF (PyMuPDF)
│   │   ├── chunking.py         # Pemotongan teks (TokenTextSplitter)
│   │   ├── embedder.py         # Embedding & penyimpan ke FAISS
│   │   └── ingestion_pipeline.py # Pipeline ingestion incremental
│   ├── retrieval/              # Pencarian dokumen relevan
│   │   └── retriever.py        # Query ke FAISS vector index
│   └── generation/             # Logika pembuatan jawaban LLM
│       └── generator.py        # Formatting prompt & OpenAI API call
├── storage/                    # Database lokal FAISS & Ingestion Manifest
│   ├── faiss_db/               # Vektor database FAISS
│   └── ingestion_manifest.json # Tracker status file PDF (MD5 hash)
├── web_app.py                  # Dashboard UI berbasis Streamlit
├── run.py                      # Entry point CLI aplikasi
├── sync_manifest.py            # Skrip sinkronisasi manifest & FAISS
├── debug_pipeline.py           # Skrip pengujian & debugging pipeline
├── requirements.txt            # Daftar dependensi Python
└── README.md                   # Dokumentasi proyek
```

---

## 🚀 Instalasi & Persiapan

### 1. Clone Repository
```bash
git clone https://github.com/username/RAG-GPT.git
cd RAG-GPT
```

### 2. Buat Virtual Environment
```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependensi
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi Environment Variable
Buat file `.env` di direktori utama (root) proyek dan isi dengan API key OpenAI Anda:
```env
OPENAI_API_KEY=sk-proj-your-openai-api-key-here
```

---

## 🎯 Cara Menjalankan Aplikasi

### 1. Menambahkan Dokumen PDF
Letakkan semua dokumen PDF internal kampus yang ingin diindeks ke dalam direktori:
```text
data/raw/
```

### 2. Menjalankan Ingestion Pipeline (Opsional)
Pipeline secara otomatis berjalan jika ada dokumen baru saat membuka aplikasi. Namun Anda bisa memprosesnya secara manual kapan saja:
```bash
python src/ingestion/ingestion_pipeline.py
```

### 3. Menjalankan Web UI (Rekomendasi)
Buka antarmuka aplikasi di browser menggunakan Streamlit:
```bash
streamlit run web_app.py
```
Aplikasi akan dapat diakses di `http://localhost:8501`.

### 4. Menjalankan Mode CLI Terminal
```bash
python run.py
```

---

## 🔧 Skrip Utilitas & Debugging

- **Sinkronisasi Manifest & Database**:
  ```bash
  python sync_manifest.py
  ```
- **Pengujian Pipeline Pemrosesan Dokumen**:
  ```bash
  python debug_pipeline.py
  ```

---

## 📄 Lisensi
Proyek ini dikembangkan untuk keperluan akademik dan penelitian Virtual Assistant Kampus berbasis RAG.
