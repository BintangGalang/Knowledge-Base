"""
rag_engine/src/generation/generator.py
Generator dengan System Prompt yang kuat + dukungan Conversation History
"""
import os
from typing import List, Optional
from dotenv import load_dotenv

load_dotenv()


class HistoryMessage:
    """Representasi satu pesan dalam history percakapan."""
    def __init__(self, role: str, content: str):
        self.role = role    # "user" atau "assistant"
        self.content = content


class Generator:
    SYSTEM_PROMPT = """Anda adalah SHAVIRA — Sistem Asisten Akademik & Hukum resmi Universitas Pendidikan Ganesha (Undiksha), Bali, Indonesia.

IDENTITAS & PERAN:
- Anda adalah asisten virtual RESMI Undiksha yang dipercaya oleh civitas akademika.
- Anda hanya menjawab pertanyaan yang berkaitan dengan Undiksha: peraturan akademik, regulasi hukum (JDIH), kebijakan kemahasiswaan, kurikulum, MOU, SOP, dan layanan kampus.

ATURAN MENJAWAB (WAJIB DIPATUHI):
1. HANYA gunakan informasi dari konteks dokumen yang diberikan. JANGAN mengarang atau berhalusinasi fakta.
2. Jika informasi tidak tersedia dalam konteks, jawab dengan jelas: "Maaf, informasi mengenai hal ini belum tersedia dalam basis pengetahuan Undiksha yang saya miliki."
3. Selalu sebut nama dokumen, nomor SK/peraturan, atau judul sumber jika tersedia dalam metadata.
4. Gunakan Bahasa Indonesia yang formal, jelas, dan mudah dipahami.
5. Jika menjawab pertanyaan tentang prosedur atau langkah-langkah, gunakan format bernomor/bullet yang rapi.
6. Di akhir jawaban, SELALU sertakan bagian "📄 Referensi Dokumen" yang mencantumkan sumber yang digunakan.

LARANGAN:
- DILARANG menjawab pertanyaan di luar konteks Undiksha (misalnya soal universitas lain, berita umum, dll).
- DILARANG memberikan opini pribadi atau informasi yang tidak ada di dokumen.
- DILARANG menginstruksikan tindakan ilegal atau tidak etis."""

    def __init__(self, model_name: str = "gpt-4o-mini"):
        from openai import OpenAI as OpenAIClient
        self.client = OpenAIClient(
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
        self.model_name = model_name

    def _build_context_str(self, nodes) -> str:
        """Format daftar node menjadi blok konteks terstruktur untuk LLM."""
        parts = []
        for i, node in enumerate(nodes):
            text = node.get_content() if hasattr(node, 'get_content') else str(node)
            meta = node.metadata if hasattr(node, 'metadata') else {}
            title = meta.get("title", "Dokumen Undiksha")
            category = meta.get("category", "")
            source_url = meta.get("source_url", "")
            section = meta.get("section_header", "")
            score = getattr(node, "score", 0.0)

            header = f"[Sumber {i+1}] {title}"
            if section:
                header += f" — {section}"
            if category:
                header += f" (Kategori: {category})"
            if source_url:
                header += f"\nURL: {source_url}"
            header += f" | Skor Relevansi: {score:.3f}"

            parts.append(f"{header}\n{text}")

        return "\n\n---\n\n".join(parts)

    def generate(
        self,
        query_str: str,
        nodes,
        history: Optional[List[HistoryMessage]] = None
    ) -> str:
        """
        Generate jawaban menggunakan RAG dengan dukungan conversation history.
        
        Args:
            query_str: Pertanyaan user saat ini.
            nodes: List node dari retriever.
            history: Opsional — list HistoryMessage untuk percakapan multi-turn.
        """
        context_str = self._build_context_str(nodes)

        # Bangun messages list untuk OpenAI Chat Completions
        messages = [{"role": "system", "content": self.SYSTEM_PROMPT}]

        # Tambahkan history percakapan (jika ada), batasi 6 pesan terakhir
        if history:
            for msg in history[-6:]:
                messages.append({"role": msg.role, "content": msg.content})

        # Tambahkan pertanyaan sekarang + konteks dokumen
        user_content = (
            f"KONTEKS DOKUMEN UNDIKSHA:\n"
            f"{'='*50}\n"
            f"{context_str}\n"
            f"{'='*50}\n\n"
            f"PERTANYAAN: {query_str}"
        )
        messages.append({"role": "user", "content": user_content})

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=2048,
                timeout=60.0
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            return f"[Error LLM] {str(e)}"