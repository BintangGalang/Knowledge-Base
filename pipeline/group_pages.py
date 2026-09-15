import json, re
from collections import defaultdict
from pathlib import Path
def is_ocr_garbage(text: str) -> bool:
    """Sama seperti Fase 1"""
    if not text or len(text.strip()) < 50:
        return True
    words = text.split()
    if len(words) < 20:
        return True
    alpha_chars = sum(1 for c in text if c.isalpha())
    total_chars = len(text.replace(" ", ""))
    if total_chars > 0 and alpha_chars / total_chars < 0.5:
        return True
    return False
def extract_real_title(pages: list, filename: str) -> str:
    """
    Ekstrak judul nyata dari halaman pertama dokumen.
    Prioritas: konten halaman 1 > nama file yang sudah dibersihkan
    """
    # Coba dari halaman pertama
    if pages:
        first_page_text = pages[0].get("text", "")
        lines = [l.strip() for l in first_page_text.split('\n') if l.strip()]
        
        for line in lines[:15]:
            # Heuristik judul: tidak terlalu pendek/panjang, bukan angka/tanggal
            if (15 < len(line) < 250 and
                not re.match(r'^\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4}', line) and
                not re.match(r'^(page|halaman|no\.|nomor|www|http)', line, re.IGNORECASE) and
                not re.match(r'^\s*[\d\s\.\,]+$', line)):
                return line.strip()
    
    # Fallback: bersihkan nama file
    clean_name = re.sub(r'[-_]\d{10,}', '', filename.replace(".pdf", ""))
    clean_name = re.sub(r'^\d{10,}[-_]?', '', clean_name)
    return clean_name.strip() or filename
def group_pages(input_file: str, output_file: str) -> dict:
    """
    Group semua halaman berdasarkan page_id.
    Output: satu baris JSONL per dokumen PDF.
    """
    # Kumpulkan semua halaman per page_id
    doc_groups = defaultdict(list)
    orphan_pages = []  # Halaman tanpa page_id
    
    print("📖 Membaca file JSONL...")
    with open(input_file, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                page_id = doc.get("metadata", {}).get("page_id", "")
                if page_id:
                    doc_groups[page_id].append(doc)
                else:
                    orphan_pages.append(doc)
            except json.JSONDecodeError:
                continue
    
    print(f"✅ Ditemukan {len(doc_groups):,} dokumen unik dari {i:,} halaman")
    
    # Susun setiap dokumen
    grouped_docs = []
    stats = {
        "total_docs": 0,
        "total_pages_processed": 0,
        "garbage_pages_filtered": 0,
        "docs_single_page": 0,
        "docs_multi_page": 0,
        "title_extracted_from_content": 0,
        "title_from_filename": 0,
    }
    
    for page_id, pages in doc_groups.items():
        # Urutkan halaman berdasarkan nomor halaman
        pages_sorted = sorted(pages, key=lambda x: x.get("metadata", {}).get("page", 0))
        
        # Filter halaman OCR garbage sebelum digabung
        good_pages = []
        garbage_count = 0
        for p in pages_sorted:
            text = p.get("text", "")
            if is_ocr_garbage(text):
                garbage_count += 1
            else:
                good_pages.append(p)
        
        stats["garbage_pages_filtered"] += garbage_count
        stats["total_pages_processed"] += len(pages_sorted)
        
        if not good_pages:
            # Dokumen seluruhnya garbage, skip
            continue
        
        # Ambil metadata dari halaman pertama sebagai referensi
        first_meta = good_pages[0].get("metadata", {})
        filename = first_meta.get("page_id", "unknown.pdf")
        raw_title = first_meta.get("title", filename)
        
        # Ekstrak judul nyata
        real_title = extract_real_title(good_pages, filename)
        if real_title != raw_title and not real_title.endswith(".pdf"):
            stats["title_extracted_from_content"] += 1
        else:
            stats["title_from_filename"] += 1
        
        # Gabungkan teks semua halaman dengan separator yang jelas
        page_separator = "\n\n--- [Halaman {page_num}] ---\n\n"
        combined_text_parts = []
        for p in good_pages:
            page_num = p.get("metadata", {}).get("page", "?")
            combined_text_parts.append(
                page_separator.format(page_num=page_num) + p.get("text", "").strip()
            )
        combined_text = "\n".join(combined_text_parts).strip()
        
        # Susun dokumen grouped
        grouped_doc = {
            "doc_id": page_id.replace(".pdf", ""),   # Akan diganti UUID di fase enrichment
            "title": real_title,
            "title_raw": raw_title,
            "text": combined_text,
            "total_pages": len(pages_sorted),
            "good_pages": len(good_pages),
            "garbage_pages_removed": garbage_count,
            "metadata": {
                "page_id": page_id,
                "url": first_meta.get("url", ""),
                "source_url": first_meta.get("url", ""),
                "target_site": first_meta.get("target_site", ""),
                "content_type": first_meta.get("content_type", "pdf"),
                "last_updated": first_meta.get("last_updated", ""),
                "parse_status": first_meta.get("parse_status", ""),
                "page_ids_included": [
                    p.get("metadata", {}).get("page", 0) for p in good_pages
                ],
                "source": "jdih.undiksha.ac.id",
            }
        }
        
        grouped_docs.append(grouped_doc)
        stats["total_docs"] += 1
        if len(pages_sorted) == 1:
            stats["docs_single_page"] += 1
        else:
            stats["docs_multi_page"] += 1
    
    # Tambahkan orphan pages sebagai dokumen tersendiri
    for p in orphan_pages:
        text = p.get("text", "")
        if not is_ocr_garbage(text):
            grouped_docs.append({
                "doc_id": f"orphan_{len(grouped_docs)}",
                "title": p.get("metadata", {}).get("title", "Dokumen Tanpa ID"),
                "title_raw": p.get("metadata", {}).get("title", ""),
                "text": text,
                "total_pages": 1,
                "good_pages": 1,
                "garbage_pages_removed": 0,
                "metadata": p.get("metadata", {}),
            })
    
    # Tulis output
    with open(output_file, "w", encoding="utf-8") as f:
        for doc in grouped_docs:
            f.write(json.dumps(doc, ensure_ascii=False) + "\n")
    
    # Laporan
    print(f"\n📊 HASIL GROUPING:")
    print(f"   Dokumen digrouping       : {stats['total_docs']:,}")
    print(f"   Total halaman diproses   : {stats['total_pages_processed']:,}")
    print(f"   Halaman garbage dibuang  : {stats['garbage_pages_filtered']:,}")
    print(f"   Dokumen 1 halaman        : {stats['docs_single_page']:,}")
    print(f"   Dokumen multi-halaman    : {stats['docs_multi_page']:,}")
    print(f"   Judul dari konten        : {stats['title_extracted_from_content']:,}")
    print(f"   Judul dari filename      : {stats['title_from_filename']:,}")
    print(f"   ✅ Output: {output_file}")
    
    return stats
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="grouped_docs.jsonl")
    args = parser.parse_args()
    group_pages(args.input, args.output)
