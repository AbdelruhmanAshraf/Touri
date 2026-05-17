"""
RAG retriever — semantic search over indexed travel documents.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def retrieve(query: str, country: str = None, n_results: int = 5, filter_type: Optional[str] = None) -> str:
    """
    Retrieve relevant documents from ChromaDB.
    Returns formatted context string with source attribution.
    """
    from rag.vector_store import get_collection, is_rag_available

    if not is_rag_available():
        return ""

    collection = get_collection()
    try:
        where = {}
        if filter_type:
            where["type"] = filter_type
        if country:
            where["country"] = country.lower()
            
        if not where:
            where = None
            
        results = collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where,
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not docs:
            return ""

        # Format with source attribution and relevance filter
        formatted = []
        for doc, meta, dist in zip(docs, metas, distances):
            # Only include reasonably relevant results (cosine distance < 0.8)
            if dist < 0.8:
                source = meta.get("file", "unknown")
                formatted.append(f"[Source: {source}]\n{doc.strip()}")

        return "\n\n---\n\n".join(formatted) if formatted else ""

    except Exception as e:
        logger.warning(f"RAG retrieval error: {e}")
        return ""
