import os
import json
from llama_index.llms.openai import OpenAI
from llama_index.core import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class RetrievalEvaluator:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = OpenAI(
            model=model_name,
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=0.0,
            max_retries=3,
        )
        
        self.eval_template = PromptTemplate(
            "Anda adalah evaluator relevansi dokumen. Tugas Anda adalah menilai apakah dokumen yang diberikan relevan untuk menjawab pertanyaan pengguna.\n"
            "Pertanyaan: {query_str}\n"
            "Dokumen:\n{context_str}\n\n"
            "Kriteria penilaian:\n"
            "- Correct: Dokumen berisi informasi yang secara langsung menjawab pertanyaan secara lengkap dan akurat.\n"
            "- Ambiguous: Dokumen berisi informasi yang terkait dengan topik, tetapi tidak cukup spesifik atau hanya menjawab sebagian pertanyaan.\n"
            "- Incorrect: Dokumen sama sekali tidak relevan dengan pertanyaan atau tidak mengandung informasi yang berguna.\n\n"
            "Output Anda HARUS berupa JSON dengan format: {{\"score\": \"Correct\" | \"Ambiguous\" | \"Incorrect\", \"reason\": \"alasan singkat\"}}\n"
            "Output:"
        )
        
    def evaluate(self, query_str: str, context_str: str) -> str:
        prompt = self.eval_template.format(query_str=query_str, context_str=context_str)
        try:
            response = self.llm.complete(prompt)
            result_text = response.text.strip()
            # Bersihkan dari markdown markdown json jika ada
            if result_text.startswith("```json"):
                result_text = result_text[7:-3]
            elif result_text.startswith("```"):
                result_text = result_text[3:-3]
            
            data = json.loads(result_text)
            return data.get("score", "Ambiguous")
        except Exception as e:
            print(f"[Evaluator Error] {e}")
            return "Ambiguous" # Default fallback
