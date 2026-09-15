import json, re
from dataclasses import dataclass
CHUNK_CONFIG = {
    "mou_perjanjian_kerjasama": {"max_tokens": 400, "overlap": 50},
    "mou": {"max_tokens": 400, "overlap": 50},
    "peraturan_kebijakan": {"max_tokens": 512, "overlap": 64},
    "peraturan": {"max_tokens": 512, "overlap": 64},
    "sk": {"max_tokens": 400, "overlap": 50},
    "pedoman_sop": {"max_tokens": 400, "overlap": 50},
    "panduan": {"max_tokens": 400, "overlap": 50},
    "silabus": {"max_tokens": 300, "overlap": 30},
    "default": {"max_tokens": 400, "overlap": 50},
}
def split_by_structure(text: str, doc_type: str) -> list[dict]:
    """
    Coba split berdasarkan struktur dokumen legal:
    - Pasal, Ayat, Bab, Klausul, Nomor urut
    """
    # Pattern struktur dokumen legal Indonesia/Inggris
    structural_patterns = [
        r'\n(?=BAB\s+[IVXLCDM]+)',          # BAB I, BAB II, dst
        r'\n(?=CHAPTER\s+[IVXLCDM]+)',       # CHAPTER I, dst
        r'\n(?=Pasal\s+\d+)',                # Pasal 1, Pasal 2, dst
        r'\n(?=Article\s+\d+)',              # Article 1, dst
        r'\n(?=\d+\.\s+[A-Z])',             # 1. Judul bab/klausul
        r'\n(?=[A-Z][A-Z\s]{5,}\n)',        # HURUF KAPITAL SEMUA (judul seksi)
    ]
    
    # Coba setiap pattern
    for pattern in structural_patterns:
        parts = re.split(pattern, text)
        if len(parts) > 2:  # Berhasil memecah lebih dari 2 bagian
            return [{"section": part.strip(), "detected_by": pattern} 
                    for part in parts if part.strip()]
    
    # Fallback: split per paragraf ganda
    paragraphs = re.split(r'\n\n+', text)
    return [{"section": p.strip(), "detected_by": "paragraph"} 
            for p in paragraphs if p.strip()]
def tokens_approx(text: str) -> int:
    """Estimasi token kasar"""
    return len(text) // 4
def merge_short_sections(sections: list[dict], max_tokens: int) -> list[str]:
    """Gabungkan seksi pendek agar tidak terlalu kecil"""
    merged = []
    current = ""
    
    for section in sections:
        text = section["section"]
        if tokens_approx(current + text) <= max_tokens:
            current = (current + "\n\n" + text).strip()
        else:
            if current:
                merged.append(current)
            current = text
    
    if current:
        merged.append(current)
    return merged
def chunk_document(doc: dict) -> list[dict]:
    """Chunk satu dokumen dan hasilkan list chunk"""
    cat = doc.get("category", "default")
    doc_type = doc.get("document_type", "default")
    # try category then doc_type then default
    config = CHUNK_CONFIG.get(cat, CHUNK_CONFIG.get(doc_type, CHUNK_CONFIG["default"]))
    max_tokens = config["max_tokens"]
    
    text = doc.get("text", "")
    doc_id = doc.get("doc_id", "unknown")
    
    # Hapus separator halaman dari Fase 2 untuk chunking bersih
    clean_text = re.sub(r'\n--- \[Halaman \d+\] ---\n', '\n\n', text)
    
    sections = split_by_structure(clean_text, doc_type)
    merged_chunks = merge_short_sections(sections, max_tokens)
    
    chunks = []
    for i, chunk_text in enumerate(merged_chunks):
        if len(chunk_text.split()) < 15:  # Skip chunk terlalu pendek
            continue
        
        # Deteksi judul seksi dari awal chunk
        first_line = chunk_text.split('\n')[0].strip()
        section_title = first_line if len(first_line) < 100 else ""
        
        chunk = {
            "chunk_id": f"{doc_id}-chunk-{i+1:04d}",
            "doc_id": doc_id,
            "chunk_index": i + 1,
            "total_chunks": len(merged_chunks),
            "text": chunk_text,
            "section_title": section_title,
            
            # Metadata dari dokumen untuk filtering di vector DB
            "title": doc.get("title", ""),
            "category": doc.get("category", ""),
            "subcategory": doc.get("subcategory", ""),
            "document_type": doc.get("document_type", ""),
            "topic_tags": doc.get("topic_tags", []),
            "target_audience": doc.get("target_audience", []),
            "language": doc.get("language", "id"),
            "confidence_level": doc.get("confidence_level", ""),
            "related_units": doc.get("related_units", []),
            "is_time_sensitive": doc.get("is_time_sensitive", False),
            "source_url": doc.get("source_url", ""),
            "target_site": doc.get("target_site", ""),
            "last_updated": doc.get("last_updated", ""),
            "doc_summary": doc.get("summary", ""),
        }
        chunks.append(chunk)
    
    # Update total_chunks yang akurat
    for chunk in chunks:
        chunk["total_chunks"] = len(chunks)
    
    return chunks
def process_jsonl(input_file: str, output_file: str):
    from tqdm import tqdm
    
    all_docs = []
    with open(input_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                all_docs.append(json.loads(line))
    
    total_chunks = 0
    with open(output_file, "w", encoding="utf-8") as fout:
        for doc in tqdm(all_docs, desc="Chunking"):
            chunks = chunk_document(doc)
            for chunk in chunks:
                fout.write(json.dumps(chunk, ensure_ascii=False) + "\n")
            total_chunks += len(chunks)
    
    print(f"\n✅ Chunking selesai:")
    print(f"   Dokumen diproses : {len(all_docs):,}")
    print(f"   Total chunk      : {total_chunks:,}")
    print(f"   Rata chunk/dokumen: {total_chunks/max(len(all_docs),1):.1f}")
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="Data/enriched_docs.jsonl")
    parser.add_argument("--output", default="Data/chunks.jsonl")
    args = parser.parse_args()
    process_jsonl(args.input, args.output)
