import os
from llama_index.llms.openai import OpenAI
from llama_index.core import PromptTemplate
from .evaluator import RetrievalEvaluator
from dotenv import load_dotenv

load_dotenv()

class CRAGWorkflow:
    def __init__(self, model_name="gpt-4o-mini"):
        self.llm = OpenAI(
            model=model_name,
            api_key=os.environ.get("OPENAI_API_KEY"),
            temperature=0.1,
            max_retries=3,
        )
        self.evaluator = RetrievalEvaluator(model_name=model_name)
        
        self.knowledge_refinement_template = PromptTemplate(
            "Tugas Anda adalah mengekstrak potongan pengetahuan yang relevan dengan pertanyaan dari dokumen berikut.\n"
            "Jika ada informasi yang relevan, tulis ulang agar ringkas dan jelas. Jika tidak ada yang relevan, kembalikan string kosong.\n"
            "Pertanyaan: {query_str}\n"
            "Dokumen:\n{context_str}\n\n"
            "Pengetahuan yang relevan (jika ada):"
        )
        
        self.query_rewrite_template = PromptTemplate(
            "Anda adalah ahli perumusan kata kunci pencarian. Rumuskan ulang pertanyaan pengguna menjadi satu atau lebih kata kunci pencarian web yang optimal.\n"
            "Hanya outputkan kata kuncinya saja, tanpa kata-kata pengantar.\n"
            "Pertanyaan pengguna: {query_str}\n"
            "Kata kunci:"
        )

    def _refine_knowledge(self, query_str: str, context_str: str) -> str:
        prompt = self.knowledge_refinement_template.format(query_str=query_str, context_str=context_str)
        response = self.llm.complete(prompt)
        return response.text.strip()

    def _rewrite_query(self, query_str: str) -> str:
        prompt = self.query_rewrite_template.format(query_str=query_str)
        response = self.llm.complete(prompt)
        return response.text.strip()

    def _web_search(self, query_str: str) -> str:
        search_results = []
        try:
            from ddgs import DDGS
            site_query = f"site:undiksha.ac.id {query_str}"
            with DDGS() as ddgs:
                results = ddgs.text(site_query, max_results=3)
                for r in results:
                    search_results.append(f"[Web: {r.get('title', 'Unknown')}]\nIsi: {r.get('body', '')}")
        except Exception as e:
            print(f"[Web Search Error] {e}")
        
        return "\n\n".join(search_results)

    def run(self, query_str: str, retrieved_nodes):
        refined_contexts = []
        process_logs = []
        
        for node in retrieved_nodes:
            content = node.get_content()
            source = node.metadata.get('file_name', 'Unknown')
            page = node.metadata.get('page_label', '-')
            node_id = node.node_id
            
            # 1. Retrieval Evaluator
            score = self.evaluator.evaluate(query_str, content)
            print(f"[Evaluator] Node {source} p.{page} - Score: {score}")
            process_logs.append({"id": node_id, "file": source, "page": page, "score": score})
            
            if score == "Correct":
                # 2. Knowledge Refinement
                refined_text = self._refine_knowledge(query_str, content)
                if refined_text:
                    refined_contexts.append(f"[Sumber: {source}, Hal: {page}]\nIsi: {refined_text}")
                    
            elif score == "Ambiguous":
                # Web Search + Knowledge Refinement (Optional web search logic here, but standard CRAG adds web search on ambiguous too)
                refined_text = self._refine_knowledge(query_str, content)
                if refined_text:
                    refined_contexts.append(f"[Sumber: {source}, Hal: {page}]\nIsi: {refined_text}")
                
                # Tambahan Web Search
                rewritten_query = self._rewrite_query(query_str)
                web_context = self._web_search(rewritten_query)
                if web_context:
                    refined_contexts.append(web_context)
                    
            elif score == "Incorrect":
                # 3. Query Rewriting & Web Search
                rewritten_query = self._rewrite_query(query_str)
                print(f"[Web Search] Memicu pencarian web dengan query: {rewritten_query}")
                web_context = self._web_search(rewritten_query)
                if web_context:
                    refined_contexts.append(web_context)
        
        # 4. Knowledge Combination
        combined_knowledge = "\n\n".join(refined_contexts)
        
        # Fallback jika pencarian web gagal dan dokumen internal tidak relevan
        if not combined_knowledge:
             combined_knowledge = "Tidak ada informasi yang ditemukan baik dari dokumen internal maupun web."
        
        return combined_knowledge, process_logs
