import json, re, unicodedata
def clean_text(text: str) -> str:
    """Pipeline cleaning untuk teks dokumen legal/hukum Undiksha"""
    
    # 1. Normalisasi unicode
    text = unicodedata.normalize("NFKC", text)
    
    # 2. Hapus karakter kontrol (kecuali newline dan tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    
    # 3. Hapus boilerplate PDF umum
    patterns_to_remove = [
        r"This document was signed electronically.*?\n",
        r"Dokumen ini ditandatangani secara elektronik.*?\n",
        r"Verified by.*?GMT[+\-]\d{2}:\d{2}\n?",
        r"\d{2}/\d{2}/\d{4}\s+\w+\s+\w+\s+\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}:\d{2}\s+GMT[+\-]\d{2}:\d{2}",
        r"(Scanned\s+(by|Image|with)[^\n]*\n?)",
        r"(Page\s+\d+\s+of\s+\d+\n?)",
        r"(Halaman\s+\d+\s+dari\s+\d+\n?)",
    ]
    for pattern in patterns_to_remove:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    # 4. Normalkan separator halaman yang ditambahkan di Fase 2
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    
    # 5. Hapus baris yang hanya berisi karakter non-bermakna
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            # Hapus baris yang hampir seluruhnya karakter khusus/angka
            alpha_ratio = sum(1 for c in stripped if c.isalpha()) / max(len(stripped), 1)
            if alpha_ratio > 0.3 or len(stripped) < 5:  # Pertahankan baris pendek (nomor, dll)
                cleaned_lines.append(line)
        else:
            cleaned_lines.append("")  # Pertahankan baris kosong untuk paragraf
    
    text = '\n'.join(cleaned_lines)
    text = re.sub(r"\n{4,}", "\n\n\n", text)  # Rapikan lagi setelah filter baris
    
    return text.strip()
def process_grouped_docs(input_file: str, output_file: str):
    cleaned = 0
    skipped = 0
    total_chars_removed = 0
    total_chars_original = 0
    
    with open(input_file, "r", encoding="utf-8") as fin, \
         open(output_file, "w", encoding="utf-8") as fout:
        
        for i, line in enumerate(fin, 1):
            line = line.strip()
            if not line:
                continue
            
            doc = json.loads(line)
            original_text = doc.get("text", "")
            cleaned_text = clean_text(original_text)
            
            if len(cleaned_text.split()) < 30:
                skipped += 1
                continue  # Buang dokumen yang terlalu pendek setelah cleaning
            
            chars_removed = len(original_text) - len(cleaned_text)
            total_chars_removed += max(chars_removed, 0)
            total_chars_original += len(original_text)
            
            doc["text"] = cleaned_text
            doc["metadata"]["char_count"] = len(cleaned_text)
            doc["metadata"]["word_count"] = len(cleaned_text.split())
            doc["metadata"]["cleaning_applied"] = True
            
            fout.write(json.dumps(doc, ensure_ascii=False) + "\n")
            cleaned += 1
            
            if i % 100 == 0:
                print(f"  Diproses: {i} dokumen...")
    
    percentage_removed = (total_chars_removed / max(total_chars_original, 1)) * 100
    
    print(f"\n✅ Cleaning selesai:")
    print(f"   Dokumen dibersihkan : {cleaned:,}")
    print(f"   Dokumen dibuang     : {skipped:,} (terlalu pendek)")
    print(f"   Total karakter awal : {total_chars_original:,}")
    print(f"   Total karakter dibuang: {total_chars_removed:,} ({percentage_removed:.2f}%)")
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="grouped_docs.jsonl")
    parser.add_argument("--output", default="cleaned_docs.jsonl")
    args = parser.parse_args()
    process_grouped_docs(args.input, args.output)
