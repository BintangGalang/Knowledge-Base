import os
import sys
from dotenv import load_dotenv

load_dotenv()

from src.ingestion.ingestion_pipeline import run_ingestion_pipeline

def start():
    # Cek apakah ada flag --force
    force_mode = "--force" in sys.argv
    
    print("Memeriksa pembaruan dokumen...")
    run_ingestion_pipeline(force=force_mode) 
    
    print("Menjalankan SHAVIRA...")
    os.system("python -m app.main")

if __name__ == "__main__":
    start()