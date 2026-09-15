import os
import sys
from dotenv import load_dotenv

# 1. Pastikan Root Project terdaftar dengan benar
root_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root_path not in sys.path:
    sys.path.insert(0, root_path)

load_dotenv()

# 2. Import Modular (Pastikan nama Class sesuai dengan isi file Anda)
try:
    from src.retrieval.retriever import Retriever
    from src.generation.generator import Generator
except ImportError as e:
    print(f"[ERROR] Gagal mengimpor modul: {e}")
    sys.exit(1)

def main():
    # Gunakan path absolut ke folder storage
    db_path = os.path.join(root_path, "storage", "faiss_db")
    
    # Validasi keberadaan database sebelum mulai
    if not os.path.exists(db_path):
        print(f"[ERROR] Database tidak ditemukan di: {db_path}")
        print("Jalankan pipeline ingestion terlebih dahulu!")
        return

    try:
        # Inisialisasi Komponen
        print("[Inisialisasi sistem...]")
        retriever = Retriever(db_path=db_path)
        generator = Generator(model_name="meta-llama/llama-3.1-8b-instruct:free")
        
        print("       SHAVIRA V1.0       ")
        print("  Virtual Campus Assistant")
        
        while True:
            query = input("\n[Tanya]: ").strip()
            
            if not query:
                continue
            if query.lower() in ['exit', 'keluar', 'quit']:
                print("Mematikan sistem. Sampai jumpa!")
                break
            
            # Tahap 1: Retrieval
            print("[Mencari dokumen relevan...]", end="\r")
            nodes = retriever.search(query)
            
            if not nodes:
                print("\n[!] Maaf, saya tidak menemukan informasi yang relevan di dokumen.")
                continue
            
            # Tahap 2: Generation
            print("[Menyusun jawaban berdasarkan konteks...]", end="\r")
            response = generator.generate(query, nodes)

            # Tampilan Jawaban
            print("\n" + "-"*15 + " JAWABAN " + "-"*15)
            print(response)
            print("-" * 39)
            
            # Tahap 3: Verifikasi Metadata & Citasi
            print("\n[Sumber Referensi]:")
            for i, node in enumerate(nodes):
                fname = node.metadata.get('file_name', 'Tidak diketahui')
                page = node.metadata.get('page_label', '?')
                # LlamaIndex nodes biasanya memiliki atribut score jika menggunakan VectorStore
                score = getattr(node, 'score', 0.0)
                print(f" ({i+1}) {fname} | Hal: {page} | Score: {score:.4f}")
            
    except Exception as e:
        print(f"\n[FATAL ERROR] Terjadi kesalahan sistem: {e}")

if __name__ == "__main__":
    main()