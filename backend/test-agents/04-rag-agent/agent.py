class RAGRetrievalAgent:
    """
    Knowledge retrieval and synthesis agent querying document embeddings.
    """
    def __init__(self, system_prompt: str = "Answer questions based only on retrieved knowledge."):
        self.system_prompt = system_prompt

    def search_knowledge_base(self, query: str, top_k: int = 3) -> list:
        """Search vectorized knowledge repository for matching document chunks."""
        return [
            {"doc_id": "DOC-101", "score": 0.94, "text": "Returns are accepted within 30 days of delivery with original packaging."},
            {"doc_id": "DOC-102", "score": 0.88, "text": "Warranty covers hardware defects for 12 months from purchase."}
        ]

    def fetch_full_document(self, doc_id: str) -> dict:
        """Retrieve full text of a knowledge document."""
        return {
            "doc_id": doc_id,
            "title": "Return and Warranty Policy 2026",
            "body": "Complete policy documentation details..."
        }
