import os
import re
import pymupdf4llm
import hashlib
import json
from pathlib import Path
from typing import Generator
from llama_index.core import Document as LlamaDocument

class DocumentLoader:
    def __init__(self):
        pass

    def _clean_text(self, text: str) -> str:
        """Pembersihan teks tingkat lanjut."""
        # Hapus spasi di akhir setiap baris (trailing spaces)
        text = re.sub(r'[ \t]+$', '', text, flags=re.MULTILINE)
        
        # Batasi baris kosong berlebih (maksimal 2 baris baru berurutan)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Hapus pagination 
        text = re.sub(r'(?i)(halaman|page)\s+\d+\s+(dari|of)\s+\d+', '', text)
        
        return text.strip()

    def _generate_file_id(self, path: str) -> str:
        """Membuat ID unik berdasarkan konten file untuk deteksi duplikasi."""
        hasher = hashlib.md5()
        with open(path, 'rb') as f:
            buf = f.read(65536)
            while len(buf) > 0:
                hasher.update(buf)
                buf = f.read(65536)
        return hasher.hexdigest()

    def load_pdf(self, path: str, save_cleaned: bool = False, cleaned_dir: str = "data/cleaned") -> Generator[LlamaDocument, None, None]:
        """Memuat file PDF dan mengonversinya ke Markdown."""
        if not os.path.isfile(path):
            print(f"[Error] File tidak ditemukan: {path}")
            return

        file_id = self._generate_file_id(path)
        
        try:
            md_text = pymupdf4llm.to_markdown(path)
            cleaned_text = self._clean_text(md_text)

            if cleaned_text:
                metadata = {
                    "file_name": os.path.basename(path),
                    "file_id": file_id,
                    "file_path": path,
                    "category": "raw_document",
                    "source_type": "pdf"
                }
                
                if save_cleaned:
                    self._save_cleaned_json(cleaned_text, metadata, path, cleaned_dir)

                yield LlamaDocument(
                    text=cleaned_text,
                    metadata=metadata
                )
        except Exception as e:
            print(f"[Fatal Error] Gagal memproses {path}: {e}")

    def load_json(self, path: str) -> Generator[LlamaDocument, None, None]:
        """Memuat file JSON atau JSONL."""
        if not os.path.isfile(path):
            print(f"[Error] File tidak ditemukan: {path}")
            return

        file_id = self._generate_file_id(path)
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                # Coba deteksi apakah ini JSONL atau JSON biasa
                content = f.read().strip()
                if not content:
                    return

                # Reset pointer
                f.seek(0)

                if content.startswith('[') or content.startswith('{'):
                    # Kemungkinan besar JSON biasa (array atau object tunggal)
                    try:
                        data = json.loads(content)
                        if isinstance(data, list):
                            for entry in data:
                                yield from self._process_json_entry(entry, path, file_id)
                        else:
                            yield from self._process_json_entry(data, path, file_id)
                    except json.JSONDecodeError:
                        # Jika gagal, coba proses sebagai JSONL baris demi baris
                        f.seek(0)
                        for line in f:
                            if line.strip():
                                try:
                                    entry = json.loads(line)
                                    yield from self._process_json_entry(entry, path, file_id)
                                except:
                                    continue
                else:
                    # Proses sebagai JSONL
                    for line in f:
                        if line.strip():
                            try:
                                entry = json.loads(line)
                                yield from self._process_json_entry(entry, path, file_id)
                            except:
                                continue
        except Exception as e:
            print(f"[Fatal Error] Gagal memproses JSON {path}: {e}")

    def _process_json_entry(self, entry, path, file_id) -> Generator[LlamaDocument, None, None]:
        """Memproses satu entri JSON menjadi LlamaDocument."""
        text = entry.get("text", "")
        metadata = entry.get("metadata", {})
        
        if not isinstance(metadata, dict):
            metadata = {"original_metadata": metadata}

        # Tambahkan metadata sistem
        metadata.update({
            "file_name": os.path.basename(path),
            "file_id": file_id,
            "file_path": path,
            "source_type": "json"
        })
        
        if text.strip():
            yield LlamaDocument(
                text=self._clean_text(text),
                metadata=metadata
            )

    def _save_cleaned_json(self, text, metadata, original_path, cleaned_dir):
        """Menyimpan hasil pembersihan ke file JSON."""
        cleaned_dir_path = Path(cleaned_dir)
        cleaned_dir_path.mkdir(parents=True, exist_ok=True)
        
        source_name = Path(original_path).stem
        json_filename = f"{source_name}.json"
        
        with open(cleaned_dir_path / json_filename, "w", encoding="utf-8") as f:
            json.dump({
                "text": text,
                "metadata": metadata
            }, f, ensure_ascii=False, indent=2)

    def load_directory(self, raw_dir: str, save_cleaned: bool = False, cleaned_dir: str = "data/cleaned") -> Generator[LlamaDocument, None, None]:
        """Generator untuk memproses seluruh folder (PDF & JSON)."""
        if not os.path.exists(raw_dir):
            print(f"[Error] Folder {raw_dir} tidak ada.")
            return

        for filename in os.listdir(raw_dir):
            full_path = os.path.join(raw_dir, filename)
            ext = filename.lower()
            
            if ext.endswith(".pdf"):
                print(f"[PROCESS] Mengambil data dari PDF: {filename}")
                yield from self.load_pdf(full_path, save_cleaned=save_cleaned, cleaned_dir=cleaned_dir)
            elif ext.endswith(".jsonl") or ext.endswith(".json"):
                print(f"[PROCESS] Mengambil data dari JSON: {filename}")
                yield from self.load_json(full_path)