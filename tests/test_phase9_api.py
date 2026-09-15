import requests
import json

BASE_URL = "http://localhost:8000/api"

def test_all():
    print("--- 0. Testing GET /admin & GET / (FastAPI Web Admin Dashboard) ---")
    res_admin = requests.get(f"http://localhost:8000/admin")
    print(f"GET /admin Status Code: {res_admin.status_code}")
    assert res_admin.status_code == 200
    assert "<title>KBMS Shavira Undiksha" in res_admin.text

    print("\n--- 1. Testing GET /api/health ---")
    res = requests.get(f"{BASE_URL}/health")
    print(f"Status Code: {res.status_code}")
    print(f"Response: {json.dumps(res.json(), indent=2)}")
    assert res.status_code == 200
    assert res.json()["status"] == "OK"

    print("\n--- 2. Testing GET /api/kb/documents ---")
    res = requests.get(f"{BASE_URL}/kb/documents")
    print(f"Status Code: {res.status_code}")
    data = res.json()
    print(f"Total Documents: {data.get('total_documents')}, Total Chunks: {data.get('total_chunks')}")
    assert res.status_code == 200

    print("\n--- 3. Testing POST /api/kb/ingest ---")
    ingest_payload = {
        "title": "SK Rektor No 999/UN48/HK/2026 tentang Uji Coba Phase 9",
        "content": "BAB I PENDAHULUAN\nPasal 1\nSistem Shavira Undiksha secara resmi mendukung pengujian otomatis FASE 9 API Backend dan Admin Dashboard Streamlit.\nPasal 2\nDokumen ini digunakan untuk membuktikan fungsi ingest dokumen baru langsung dapat diquery secara real-time.",
        "category": "peraturan_kebijakan",
        "subcategory": "uji_coba",
        "document_type": "sk",
        "topic_tags": ["undiksha", "phase9", "uji_coba"],
        "target_audience": ["mahasiswa", "dosen"]
    }
    res = requests.post(f"{BASE_URL}/kb/ingest", json=ingest_payload)
    print(f"Status Code: {res.status_code}")
    print(f"Response: {json.dumps(res.json(), indent=2)}")
    assert res.status_code == 200
    doc_id = res.json()["doc_id"]

    print(f"\n--- 3b. Testing GET /api/kb/documents/{doc_id} (Fetch All Chunks) ---")
    res_detail = requests.get(f"{BASE_URL}/kb/documents/{doc_id}")
    print(f"Status Code: {res_detail.status_code}")
    detail_data = res_detail.json()
    print(f"Doc Title: {detail_data['document']['title']}, Total Chunks Fetched: {len(detail_data['chunks'])}")
    assert res_detail.status_code == 200
    assert len(detail_data["chunks"]) == 3

    print("\n--- 3c. Testing POST /api/kb/ingest-file (Upload File PDF/TXT) ---")
    file_content = b"BAB I UMUM\nPasal 1\nUji coba unggahan file PDF dan DOCX secara otomatis pada KBMS Shavira Undiksha.\nPasal 2\nDokumen file ini langsung diekstrak dan di-embed ke dalam Qdrant."
    files = {"file": ("Pedoman_Uji_Coba_File_Upload.txt", file_content, "text/plain")}
    data = {"category": "pedoman_sop", "document_type": "panduan"}
    res_file = requests.post(f"{BASE_URL}/kb/ingest-file", files=files, data=data)
    print(f"Status Code: {res_file.status_code}")
    print(f"Response: {json.dumps(res_file.json(), indent=2)}")
    assert res_file.status_code == 200
    assert res_file.json()["status"] == "success"
    file_doc_id = res_file.json()["doc_id"]

    print(f"\n--- 3d. Testing DELETE /api/kb/documents/{file_doc_id} ---")
    res_del = requests.delete(f"{BASE_URL}/kb/documents/{file_doc_id}")
    print(f"Status Code: {res_del.status_code}")
    print(f"Response: {json.dumps(res_del.json(), indent=2)}")
    assert res_del.status_code == 200
    assert res_del.json()["status"] == "success"

    print("\n--- 4. Testing POST /api/chat (Querying new document) ---")
    chat_payload = {
        "query": "Apa isi Pasal 1 SK Rektor No 999 tentang Uji Coba Phase 9?",
        "top_k": 3
    }
    res = requests.post(f"{BASE_URL}/chat", json=chat_payload)
    print(f"Status Code: {res.status_code}")
    chat_res = res.json()
    print(f"Answer: {chat_res['answer']}")
    print(f"Top Score: {chat_res['confidence_score']}")
    print(f"Sources Count: {len(chat_res['sources'])}")
    assert res.status_code == 200

    print("\n--- 6. Testing GET /api/crawler/status ---")
    res_crawl_status = requests.get(f"{BASE_URL}/crawler/status")
    print(f"Status Code: {res_crawl_status.status_code}")
    print(f"Response: {json.dumps(res_crawl_status.json(), indent=2)}")
    assert res_crawl_status.status_code == 200

    print("\n--- 7. Testing GET /api/crawler/pages ---")
    res_crawl_pages = requests.get(f"{BASE_URL}/crawler/pages")
    print(f"Status Code: {res_crawl_pages.status_code}")
    print(f"Total Crawled Pages: {res_crawl_pages.json().get('total_crawled')}")
    assert res_crawl_pages.status_code == 200

    print("\n[SUCCESS] ALL CHECKPOINT 9 API & CRAWLER TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_all()

