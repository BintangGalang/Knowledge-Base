import os
import json
from typing import Generator, List
from pathlib import Path
from llama_index.core import Document as LlamaDocument
from llama_index.core.node_parser import TokenTextSplitter

def chunk_documents(
    documents: Generator[LlamaDocument, None, None],
    chunk_size: int = 512, 
    overlap: int = 50,
    chunk_dir: str = "data/chunk",
    save_to_json: bool = False # Default dimatikan agar tidak mengotori disk
) -> Generator[LlamaDocument, None, None]:
    """
    Memecah dokumen menjadi potongan (nodes) berbasis jumlah token (Token Text Splitter).
    Menggunakan Generator agar hemat RAM.
    """
    chunk_dir_path = Path(chunk_dir)
    if save_to_json:
        chunk_dir_path.mkdir(parents=True, exist_ok=True)

    # Menggunakan TokenTextSplitter untuk pemotongan berbasis token kaku (fixed token chunking)
    splitter = TokenTextSplitter(
        chunk_size=chunk_size, 
        chunk_overlap=overlap
    )

    for doc in documents:
        # Memecah dokumen menjadi nodes (chunks)
        nodes = splitter.get_nodes_from_documents([doc])
        
        chunks_data = []
        for idx, node in enumerate(nodes):
            # Wariskan metadata asli dan tambahkan detail chunk
            node.metadata.update({
                "chunk_index": idx + 1,
                "chunk_size_chars": len(node.text)
            })
            
            chunks_data.append({
                "chunk_index": idx + 1,
                "text": node.text,
                "metadata": node.metadata
            })

            # Yield sebagai LlamaDocument untuk tahap embedding
            yield LlamaDocument(text=node.text, metadata=node.metadata)

        # Simpan semua chunks dari satu dokumen ke file .jsonl (JSON Lines)
        if save_to_json and chunks_data:
            source_name = Path(doc.metadata.get("file_name", "unknown")).stem
            chunk_filename = f"{source_name}_chunks.jsonl"
            
            with open(chunk_dir_path / chunk_filename, "w", encoding="utf-8") as f:
                for chunk in chunks_data:
                    f.write(json.dumps(chunk, ensure_ascii=False) + "\n")