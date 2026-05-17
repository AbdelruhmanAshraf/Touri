"""RAG search tool — wraps the retriever for use by agents."""

from rag.retriever import retrieve


def rag_search(query: str, country: str = None, filter_type: str = None) -> str:
    """
    Search the travel knowledge base (ChromaDB).
    Returns relevant context from markdown guides and dataset summaries.
    """
    result = retrieve(query, country=country, n_results=5, filter_type=filter_type)
    if not result:
        return "No relevant information found in the knowledge base."
    return f"📚 **Knowledge Base Results:**\n\n{result}"
