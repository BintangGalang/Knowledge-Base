import json, re, hashlib, argparse
from collections import defaultdict, Counter
from datetime import datetime
def is_ocr_garbage(text: str) -> bool:
    """
    Deteksi halaman yang isinya sampah OCR atau tidak bermakna.
    Kriteria: terlalu pendek, rasio karakter non-alfabet tinggi, atau
    hanya berisi metadata PDF seperti timestamp/nama author.
    """
    if not text or len(text.strip()) < 50:
        return True
    
    words = text.split()
    if len(words) < 20:
        return True
    
    # Cek rasio angka dan karakter khusus yang terlalu tinggi
    alpha_chars = sum(1 for c in text if c.isalpha())
    total_chars = len(text.replace(" ", ""))
    if total_chars > 0 and alpha_chars / total_chars < 0.5:
        return True
    
    # Pattern umum di halaman scan rusak Undiksha
    garbage_patterns = [
        r"^\s*\d{2}/\d{2}/\d{4}\s+\w+\s+\w+\s+\d{2}\.\d{2}\.\d{4}",  # timestamp OCR
        r"^Scanned\s+(by|Image|with)",
        r"^\s*[\d\.\s:GMT+]+$",  # hanya timestamp
    ]
    for pattern in garbage_patterns:
        if re.search(pattern, text[:200], re.IGNORECASE | re.MULTILINE):
            if len(words) < 50:  # Hanya tandai garbage jika konten memang sedikit
                return True
    
    return False
def extract_real_title(text: str, filename_title: str) -> str:
    """
    Coba ekstrak judul nyata dari konten teks halaman pertama.
    Jika gagal, kembalikan filename_title.
    """
    if filename_title and not filename_title.endswith(".pdf") and filename_title != "Scanned Image":
        return filename_title
    
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    
    # Cari baris yang kemungkinan judul (huruf kapital, panjang wajar)
    for line in lines[:10]:
        if (10 < len(line) < 200 and 
            not re.match(r'^\d', line) and
            not re.match(r'^(page|halaman|no\.|nomor)', line, re.IGNORECASE)):
            return line
    
    return filename_title or "Judul Tidak Diketahui"
def audit_jsonl(filepath: str) -> dict:
    stats = {
        "total_lines": 0,
        "unique_documents": set(),  # unique page_id
        "pages_per_doc": defaultdict(list),
        "target_sites": Counter(),
        "content_types": Counter(),
        "parse_status": Counter(),
        "text_length": {"min": float('inf'), "max": 0, "total": 0},
        "word_count": {"min": float('inf'), "max": 0, "total": 0},
        "issues": {
            "missing_text": [],
            "ocr_garbage": [],
            "title_is_filename": [],
            "title_is_scanned": [],
            "missing_page_id": [],
            "parse_failed": [],
        },
        "estimated_tokens": 0,
        "date_range": {"earliest": None, "latest": None},
    }
    
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            
            try:
                doc = json.loads(line)
            except json.JSONDecodeError:
                stats["issues"]["parse_failed"].append(i)
                continue
            
            stats["total_lines"] += 1
            
            text = doc.get("text", "")
            meta = doc.get("metadata", {})
            page_id = meta.get("page_id", "")
            title = meta.get("title", "")
            page_num = meta.get("page", 0)
            
            # Track unique documents
            if page_id:
                stats["unique_documents"].add(page_id)
                stats["pages_per_doc"][page_id].append(page_num)
            else:
                stats["issues"]["missing_page_id"].append(i)
            
            # Target site & content type
            stats["target_sites"][meta.get("target_site", "unknown")] += 1
            stats["content_types"][meta.get("content_type", "unknown")] += 1
            stats["parse_status"][meta.get("parse_status", "unknown")] += 1
            
            # Text analysis
            if not text or not text.strip():
                stats["issues"]["missing_text"].append(i)
            else:
                char_len = len(text)
                word_count = len(text.split())
                
                stats["text_length"]["min"] = min(stats["text_length"]["min"], char_len)
                stats["text_length"]["max"] = max(stats["text_length"]["max"], char_len)
                stats["text_length"]["total"] += char_len
                stats["word_count"]["min"] = min(stats["word_count"]["min"], word_count)
                stats["word_count"]["max"] = max(stats["word_count"]["max"], word_count)
                stats["word_count"]["total"] += word_count
                stats["estimated_tokens"] += char_len // 4
                
                if is_ocr_garbage(text):
                    stats["issues"]["ocr_garbage"].append({
                        "line": i,
                        "page_id": page_id,
                        "page": page_num,
                        "preview": text[:100]
                    })
            
            # Title analysis
            if title:
                if title.endswith(".pdf"):
                    stats["issues"]["title_is_filename"].append(i)
                elif title.lower() in ["scanned image", "scanned", "image"]:
                    stats["issues"]["title_is_scanned"].append(i)
            
            # Date tracking
            last_updated = meta.get("last_updated", "")
            if last_updated:
                try:
                    dt = datetime.strptime(last_updated, "%a, %d %b %Y %H:%M:%S GMT")
                    if not stats["date_range"]["earliest"] or dt < stats["date_range"]["earliest"]:
                        stats["date_range"]["earliest"] = dt
                    if not stats["date_range"]["latest"] or dt > stats["date_range"]["latest"]:
                        stats["date_range"]["latest"] = dt
                except:
                    pass
    
    # Hitung distribusi halaman per dokumen
    pages_dist = Counter()
    for pages in stats["pages_per_doc"].values():
        count = len(pages)
        if count == 1:
            pages_dist["1 halaman"] += 1
        elif count <= 5:
            pages_dist["2-5 halaman"] += 1
        elif count <= 10:
            pages_dist["6-10 halaman"] += 1
        elif count <= 20:
            pages_dist["11-20 halaman"] += 1
        else:
            pages_dist[f">20 halaman ({count})"] += 1
    
    stats["pages_distribution"] = dict(pages_dist)
    stats["unique_doc_count"] = len(stats["unique_documents"])
    stats["text_length"]["avg"] = stats["text_length"]["total"] // max(stats["total_lines"], 1)
    stats["word_count"]["avg"] = stats["word_count"]["total"] // max(stats["total_lines"], 1)
    del stats["unique_documents"]  # Tidak perlu print set
    del stats["pages_per_doc"]
    
    return stats
def print_report(stats: dict, filepath: str):
    print("\n" + "=" * 65)
    print("📊 LAPORAN AUDIT JSONL UNDIKSHA")
    print(f"   File: {filepath}")
    print("=" * 65)
    
    print(f"\n📄 VOLUME DATA:")
    print(f"   Total baris (halaman)  : {stats['total_lines']:,}")
    print(f"   Total dokumen unik     : {stats['unique_doc_count']:,}")
    print(f"   Estimasi total token   : {stats['estimated_tokens']:,}")
    
    print(f"\n📏 PANJANG TEKS PER HALAMAN:")
    print(f"   Min  : {stats['text_length']['min']:,} karakter")
    print(f"   Max  : {stats['text_length']['max']:,} karakter")
    print(f"   Rata : {stats['text_length']['avg']:,} karakter")
    print(f"   Min kata  : {stats['word_count']['min']:,} kata")
    print(f"   Max kata  : {stats['word_count']['max']:,} kata")
    print(f"   Rata kata : {stats['word_count']['avg']:,} kata")
    
    print(f"\n📚 DISTRIBUSI HALAMAN PER DOKUMEN:")
    for bucket, count in stats["pages_distribution"].items():
        print(f"   {bucket}: {count} dokumen")
    
    print(f"\n🌐 TARGET SITE:")
    for site, count in stats["target_sites"].most_common():
        print(f"   {site}: {count:,} halaman")
    
    print(f"\n⚠️  MASALAH DITEMUKAN:")
    issues = stats["issues"]
    print(f"   ❌ Teks kosong/hilang       : {len(issues['missing_text'])} halaman")
    print(f"   ❌ OCR garbage/rusak        : {len(issues['ocr_garbage'])} halaman")
    print(f"   ⚠️  Title hanya nama file    : {len(issues['title_is_filename'])} halaman")
    print(f"   ⚠️  Title 'Scanned Image'   : {len(issues['title_is_scanned'])} halaman")
    print(f"   ⚠️  Missing page_id         : {len(issues['missing_page_id'])} halaman")
    
    if stats["date_range"]["earliest"] and stats["date_range"]["latest"]:
        print(f"\n📅 RENTANG TANGGAL:")
        print(f"   Terlama  : {stats['date_range']['earliest'].strftime('%d %B %Y')}")
        print(f"   Terbaru  : {stats['date_range']['latest'].strftime('%d %B %Y')}")
    
    # Sampel OCR garbage
    if issues["ocr_garbage"]:
        print(f"\n🔍 CONTOH HALAMAN OCR GARBAGE (5 pertama):")
        for sample in issues["ocr_garbage"][:5]:
            print(f"   Line {sample['line']} | {sample['page_id']} hal.{sample['page']}")
            print(f"   Preview: \"{sample['preview']}\"")
            print()
    
    print("=" * 65)
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="Path ke file JSONL")
    args = parser.parse_args()
    
    stats = audit_jsonl(args.input)
    print_report(stats, args.input)
    
    # Simpan laporan ke file
    output_path = args.input.replace(".jsonl", "_audit_report.json")
    with open(output_path, "w", encoding="utf-8") as f:
        # Convert datetime objects
        if stats["date_range"]["earliest"]:
            stats["date_range"]["earliest"] = stats["date_range"]["earliest"].isoformat()
        if stats["date_range"]["latest"]:
            stats["date_range"]["latest"] = stats["date_range"]["latest"].isoformat()
        json.dump(stats, f, ensure_ascii=False, indent=2)
    print(f"\n✅ Laporan disimpan ke: {output_path}")
