import json, uuid, os, random
from datetime import datetime
from openai import OpenAI
ENRICHMENT_PROMPT = """
Kamu adalah sistem klasifikasi dokumen untuk Universitas Pendidikan Ganesha (Undiksha) Indonesia.
...
"""
def parse_last_updated(date_str: str) -> str:
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    except:
        return date_str

class DummyLLMClient:
    class chat:
        class completions:
            @staticmethod
            def create(*args, **kwargs):
                class Msg:
                    def __init__(self):
                        dummy_res = {
                          "category": random.choice(["mou_perjanjian_kerjasama", "peraturan_kebijakan", "pedoman_sop"]),
                          "subcategory": "akademik",
                          "document_type": "peraturan",
                          "topic_tags": ["hukum", "undiksha", "kerjasama"],
                          "target_audience": ["dosen", "mahasiswa"],
                          "language": "id",
                          "confidence_level": "official",
                          "related_units": ["Fakultas Hukum"],
                          "is_time_sensitive": False,
                          "summary_id": "Dokumen ini merupakan aturan atau kesepakatan resmi dari institusi terkait pelaksanaan program dan tata tertib akademik di lingkungan kampus.",
                          "keywords": ["peraturan", "kampus", "akademik", "standar", "pedoman"],
                          "qa_pairs": [
                            {"q": "Apa tujuan utama dari dokumen ini?", "a": "Mengatur pelaksanaan program dan tata tertib akademik."},
                            {"q": "Siapa saja target audiens dokumen ini?", "a": "Dosen dan Mahasiswa di lingkungan kampus."},
                            {"q": "Kapan dokumen ini mulai berlaku?", "a": "Berlaku sejak tanggal ditetapkan oleh rektorat."}
                          ]
                        }
                        self.content = json.dumps(dummy_res)
                class Choice:
                    def __init__(self):
                        self.message = Msg()
                class Resp:
                    def __init__(self):
                        self.choices = [Choice()]
                return Resp()

def enrich_document(doc: dict, llm_client, model: str) -> dict:
    text = doc.get("text", "")
    title = doc.get("title", "")
    content_preview = " ".join(text.split()[:500])
    
    try:
        response = llm_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Kamu adalah sistem klasifikasi dokumen. Jawab hanya dengan JSON valid."},
                {"role": "user", "content": f"Judul: {title}\nPreview: {content_preview}"}
            ],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        enrichment = json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"  ⚠️  Enrichment gagal untuk '{title[:50]}': {e}")
        enrichment = {
            "category": "lainnya",
            "subcategory": "tidak_terklasifikasi",
            "document_type": "lainnya",
            "topic_tags": [],
            "target_audience": ["umum"],
            "language": "id",
            "confidence_level": "informational",
            "related_units": [],
            "is_time_sensitive": False,
            "summary_id": "",
            "keywords": [],
            "qa_pairs": [],
        }
    
    meta = doc.get("metadata", {})
    
    enriched = {
        "doc_id": str(uuid.uuid4()),
        "title": doc.get("title", ""),
        "title_raw": doc.get("title_raw", ""),
        "text": text,
        "category": enrichment.get("category", "lainnya"),
        "subcategory": enrichment.get("subcategory", ""),
        "document_type": enrichment.get("document_type", "lainnya"),
        "topic_tags": enrichment.get("topic_tags", []),
        "target_audience": enrichment.get("target_audience", ["umum"]),
        "language": enrichment.get("language", "id"),
        "confidence_level": enrichment.get("confidence_level", "informational"),
        "related_units": enrichment.get("related_units", []),
        "is_time_sensitive": enrichment.get("is_time_sensitive", False),
        "summary": enrichment.get("summary_id", ""),
        "keywords": enrichment.get("keywords", []),
        "qa_pairs": enrichment.get("qa_pairs", []),
        "source_url": meta.get("url", ""),
        "page_id": meta.get("page_id", ""),
        "target_site": meta.get("target_site", "jdih.undiksha.ac.id"),
        "last_updated": parse_last_updated(meta.get("last_updated", "")),
        "total_pages": doc.get("total_pages", 1),
        "char_count": len(text),
        "word_count": len(text.split()),
        "estimated_tokens": len(text) // 4,
        "processing_version": "1.0",
        "enriched_at": datetime.utcnow().isoformat() + "Z",
    }
    
    return enriched

def process_jsonl(input_file: str, output_file: str, llm_client, model: str,
                  batch_size: int = 1, checkpoint_every: int = 50):
    from tqdm import tqdm
    checkpoint_file = output_file + ".checkpoint"
    processed_ids = set()
    try:
        with open(checkpoint_file) as f:
            processed_ids = set(json.load(f))
        print(f"📌 Resume dari checkpoint: {len(processed_ids)} dokumen sudah diproses")
    except FileNotFoundError:
        pass
    
    docs_to_process = []
    with open(input_file, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                doc = json.loads(line)
                doc_key = doc.get("metadata", {}).get("page_id", "")
                if doc_key not in processed_ids:
                    docs_to_process.append(doc)
    
    print(f"📄 {len(docs_to_process)} dokumen perlu diproses")
    
    processed_count = 0
    with open(output_file, "a", encoding="utf-8") as fout:
        for doc in tqdm(docs_to_process, desc="Enriching"):
            enriched = enrich_document(doc, llm_client, model)
            fout.write(json.dumps(enriched, ensure_ascii=False) + "\n")
            
            page_id = doc.get("metadata", {}).get("page_id", "")
            if page_id:
                processed_ids.add(page_id)
            processed_count += 1
            
            if processed_count % checkpoint_every == 0:
                with open(checkpoint_file, "w") as fc:
                    json.dump(list(processed_ids), fc)
    
    print(f"\n✅ Enrichment selesai: {processed_count} dokumen")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="Data/cleaned_docs.jsonl")
    parser.add_argument("--output", default="Data/enriched_docs.jsonl")
    parser.add_argument("--model", default="gpt-4o-mini")
    args = parser.parse_args()
    
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("ℹ️  OPENAI_API_KEY tidak ditemukan. Menggunakan Dummy LLM untuk simulasi enrichment.")
        client = DummyLLMClient()
    else:
        client = OpenAI(api_key=api_key)
        
    process_jsonl(args.input, args.output, client, args.model)
