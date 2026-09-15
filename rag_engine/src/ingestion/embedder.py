import os
import sys
import time
import faiss
from dotenv import load_dotenv

load_dotenv()

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import Document as LlamaDocument
from typing import List

EMBED_MODEL_NAME = "intfloat/multilingual-e5-large"
BATCH_SIZE = 32  # Jumlah dokumen per batch embedding 

def _format_time(seconds: float) -> str:
    """Format detik menjadi format jam:menit:detik yang mudah dibaca."""
    if seconds < 60:
        return f"{seconds:.0f}s" 
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    else:
        h, remainder = divmod(int(seconds), 3600)
        m, s = divmod(remainder, 60)
        return f"{h}h {m}m {s}s"

def _print_progress(current: int, total: int, start_time: float):
    """Cetak progress bar dengan persentase, waktu berlalu, dan estimasi selesai."""
    elapsed = time.time() - start_time
    percent = (current / total) * 100

    # Hitung ETA
    if current > 0:
        rate = elapsed / current  # detik per chunk
        remaining = (total - current) * rate
        eta_str = _format_time(remaining)
    else:
        eta_str = "menghitung..."

    # Progress bar visual (lebar 30 karakter)
    bar_length = 30
    filled = int(bar_length * current // total)
    bar = "#" * filled + "-" * (bar_length - filled)

    # Gunakan \r untuk overwrite baris yang sama
    sys.stdout.write(
        f"\r  [{bar}] {percent:5.1f}% | {current}/{total} chunks "
        f"| Waktu: {_format_time(elapsed)} | ETA: {eta_str}   "
    )
    sys.stdout.flush()

    # Newline saat selesai
    if current == total:
        print()


def save_to_vector_store(documents: List[LlamaDocument], db_path: str = "storage/faiss_db"):
    if not documents:
        print("[Warning] Tidak ada dokumen untuk disimpan.")
        return None

    total_docs = len(documents)

    # 1. Pastikan direktori ada
    os.makedirs(db_path, exist_ok=True)

    # 2. Inisialisasi FAISS index dengan dimensi 1024 (intfloat/multilingual-e5-large)
    d = 1024
    faiss_index = faiss.IndexFlatL2(d)

    # 3. Hubungkan ke LlamaIndex
    vector_store = FaissVectorStore(faiss_index=faiss_index)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    # 4. Inisialisasi model embedding
    embed_model = HuggingFaceEmbedding(model_name=EMBED_MODEL_NAME)

    print(f"\n[INFO] Memulai proses embedding untuk {total_docs} chunks...")
    print(f"[INFO] Model: {EMBED_MODEL_NAME} | Batch size: {BATCH_SIZE}")
    print(f"[INFO] Total batch: {(total_docs + BATCH_SIZE - 1) // BATCH_SIZE}\n")

    # 5. Proses per batch dengan progress tracking
    start_time = time.time()
    processed = 0

    for i in range(0, total_docs, BATCH_SIZE):
        batch = documents[i : i + BATCH_SIZE]

        # Embed dan masukkan batch ke index
        # Batch pertama: buat index, batch selanjutnya: insert ke index yang sudah ada
        if i == 0:
            index = VectorStoreIndex.from_documents(
                batch,
                storage_context=storage_context,
                embed_model=embed_model,
                show_progress=False
            )
        else:
            for doc in batch:
                index.insert(doc)

        processed += len(batch)
        _print_progress(processed, total_docs, start_time)

    # 6. Ringkasan akhir
    elapsed = time.time() - start_time
    print(f"\n[DONE] Embedding selesai dalam {_format_time(elapsed)}")
    print(f"[DONE] Kecepatan: {total_docs / elapsed:.1f} chunks/detik")

    # CRITICAL: Paksa simpan ke disk
    storage_context.persist(persist_dir=db_path)
    
    print(f"[SUCCESS] {total_docs} data tersimpan di {db_path}")
    return index