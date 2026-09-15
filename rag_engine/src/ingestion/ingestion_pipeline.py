import os
import sys
import json
import hashlib
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from loader import DocumentLoader
from chunking import chunk_documents
from embedder import save_to_vector_store

MANIFEST_PATH = "storage/ingestion_manifest.json"


def _compute_file_hash(filepath: str) -> str:
    """Hitung MD5 hash dari file untuk mendeteksi perubahan."""
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read(65536)
        while buf:
            hasher.update(buf)
            buf = f.read(65536)
    return hasher.hexdigest()


def _load_manifest() -> dict:
    """Muat manifest file yang sudah pernah diproses."""
    if os.path.exists(MANIFEST_PATH):
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_manifest(manifest: dict):
    """Simpan manifest ke disk."""
    os.makedirs(os.path.dirname(MANIFEST_PATH), exist_ok=True)
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _get_faiss_count(db_path: str = "storage/faiss_db") -> int:
    """Cek keberadaan dokumen yang sudah tersimpan di FAISS."""
    index_path = os.path.join(db_path, "default__vector_store.json")
    if os.path.exists(index_path):
        return 1
    return 0


def _find_new_or_changed_files(raw_dir: str, manifest: dict) -> list:
    """Temukan file yang baru atau berubah dibanding manifest terakhir."""
    new_files = []
    for filename in os.listdir(raw_dir):
        if filename.startswith("."):
            continue
        full_path = os.path.join(raw_dir, filename)
        if not os.path.isfile(full_path):
            continue

        ext = filename.lower()
        if not (ext.endswith(".pdf") or ext.endswith(".jsonl") or ext.endswith(".json")):
            continue

        current_hash = _compute_file_hash(full_path)
        previous_hash = manifest.get(filename, {}).get("hash", "")

        if current_hash != previous_hash:
            new_files.append({
                "filename": filename,
                "full_path": full_path,
                "hash": current_hash,
                "is_new": previous_hash == ""
            })

    return new_files


def run_ingestion_pipeline(data_path="data/raw", force=False):
    """
    Pipeline ingestion dengan deteksi perubahan.
    
    Args:
        data_path: Path ke direktori raw data
        force: Jika True, paksa re-proses semua file (abaikan manifest)
    """
    manifest = _load_manifest()
    existing_count = _get_faiss_count()

    # --- Cek apakah perlu proses ulang ---
    if not force:
        changed_files = _find_new_or_changed_files(data_path, manifest)

        if not changed_files and existing_count > 0:
            print(f"\n[SKIP] Tidak ada perubahan pada data raw.")
            print(f"[INFO] FAISS DB sudah ada dan siap digunakan.")
            print(f"[TIP]  Gunakan flag --force untuk memaksa re-proses semua data.\n")
            return None

        if changed_files:
            new_count = sum(1 for f in changed_files if f["is_new"])
            mod_count = len(changed_files) - new_count
            print(f"\n[INFO] Ditemukan perubahan:")
            if new_count > 0:
                print(f"  + {new_count} file baru")
            if mod_count > 0:
                print(f"  ~ {mod_count} file berubah")
            for f in changed_files:
                status = "BARU" if f["is_new"] else "BERUBAH"
                print(f"  [{status}] {f['filename']}")
        else:
            # Tidak ada data di ChromaDB tapi semua file ada di manifest
            # Ini berarti ChromaDB dihapus manual, perlu re-embed
            print(f"\n[INFO] FAISS DB kosong, memulai re-embedding dari data chunk yang ada...")
    else:
        print(f"\n[INFO] Mode --force aktif, memproses ulang semua data...")
        changed_files = _find_new_or_changed_files(data_path, {})  # kosongkan manifest = semua dianggap baru

    # --- Proses file yang perlu diperbarui ---
    print(f"\n[1/3] Memulai pemindaian direktori: {data_path}")

    loader_obj = DocumentLoader()
    try:
        if force or not changed_files:
            # Force mode atau FAISS DB kosong: proses semua file
            docs_gen = loader_obj.load_directory(data_path, save_cleaned=True, cleaned_dir="data/cleaned")
            files_to_update = _find_new_or_changed_files(data_path, {})
        else:
            # Hanya proses file yang berubah
            docs_gen = _load_specific_files(loader_obj, changed_files)
            files_to_update = changed_files

        chunks_gen = chunk_documents(docs_gen, save_to_json=True, chunk_dir="data/chunk")

        # Konversi ke List
        all_chunks = list(chunks_gen)
        print(f"[2/3] Ekstraksi selesai. Terbentuk {len(all_chunks)} chunks.")

        if len(all_chunks) > 0:
            # Simpan ke Vector Store
            print("[3/3] Memasukkan data ke FAISS...")
            index = save_to_vector_store(all_chunks)

            # Update manifest untuk file yang berhasil diproses
            for f in files_to_update:
                manifest[f["filename"]] = {
                    "hash": f["hash"],
                    "chunks_generated": len(all_chunks)  # Ini count total, bukan per file
                }
            _save_manifest(manifest)

            print("\n[SUKSES] Database telah diperbarui dan siap digunakan!")
            return index
        else:
            print("[PERINGATAN] Tidak ada data baru yang diproses. Pastikan file tidak kosong.")
            return None

    except Exception as e:
        print(f"[ERROR] Pipeline gagal: {e}")
        import traceback
        traceback.print_exc()
        return None


def _load_specific_files(loader_obj: DocumentLoader, files: list):
    """Generator untuk memuat hanya file-file tertentu."""
    for f in files:
        filename = f["filename"]
        full_path = f["full_path"]
        ext = filename.lower()

        if ext.endswith(".pdf"):
            print(f"[PROCESS] Mengambil data dari PDF: {filename}")
            yield from loader_obj.load_pdf(full_path, save_cleaned=True, cleaned_dir="data/cleaned")
        elif ext.endswith(".jsonl") or ext.endswith(".json"):
            print(f"[PROCESS] Mengambil data dari JSON: {filename}")
            yield from loader_obj.load_json(full_path)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Paksa re-proses semua data")
    args = parser.parse_args()
    run_ingestion_pipeline(force=args.force)