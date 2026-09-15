import os
import sys
import traceback

os.environ['TRANSFORMERS_OFFLINE'] = '1'
os.environ['HF_HUB_OFFLINE'] = '1'

sys.path.insert(0, '.')

try:
    from dotenv import load_dotenv
    load_dotenv()
    print("Step 1: dotenv OK")
except Exception as e:
    print(f"Step 1 FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    from src.retrieval.retriever import Retriever
    print("Step 2: import Retriever OK")
except Exception as e:
    print(f"Step 2 FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

try:
    r = Retriever(db_path='storage/faiss_db')
    print("Step 3: Retriever init OK")
except Exception as e:
    print(f"Step 3 FAILED: {e}")
    traceback.print_exc()
    sys.exit(1)

print("ALL OK!")
