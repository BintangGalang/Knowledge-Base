import os
import sys

from src.retrieval.retriever import Retriever
from src.generation.generator import Generator

def main():
    print("Inisialisasi Retriever...", flush=True)
    r = Retriever()
    query = "Perjanjian kerjasama fakultas ilmu sosial"
    
    print(f"Mencari dokumen untuk: '{query}'", flush=True)
    nodes = r.search(query, top_k=3)
    
    print(f"Ditemukan {len(nodes)} nodes.", flush=True)
    if not nodes:
        print("Tidak ada hasil dari qdrant.")
        return
        
    for i, n in enumerate(nodes):
        print(f"Node {i+1}: Score={n.score:.3f} Title={n.metadata.get('title')}", flush=True)

    print("\nInisialisasi Generator...", flush=True)
    g = Generator()
    
    print("Generate jawaban...", flush=True)
    resp = g.generate(query, nodes)
    print("\n=== JAWABAN ===")
    print(str(resp))

if __name__ == "__main__":
    main()
