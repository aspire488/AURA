import time

import chromadb

from app.config import settings


class ChromaService:
    def __init__(self):
        if hasattr(chromadb, "HttpClient"):
            self.client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )
        else:
            self.client = chromadb.Client(
                host=settings.chroma_host,
                port=settings.chroma_port,
            )

    async def check_health(self) -> tuple[str, float]:
        start = time.perf_counter()
        try:
            if hasattr(self.client, "heartbeat"):
                self.client.heartbeat()
            elif hasattr(self.client, "server_info"):
                self.client.server_info()
            elapsed = (time.perf_counter() - start) * 1000
            return "up", round(elapsed, 1)
        except Exception:
            elapsed = (time.perf_counter() - start) * 1000
            return "down", round(elapsed, 1)

    def upsert(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        collection = self.client.get_or_create_collection(name="conversations")
        collection.upsert(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

    def query(self, embedding: list[float], top_k: int = 5) -> list[dict]:
        collection = self.client.get_or_create_collection(name="conversations")
        result = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
        )
        items: list[dict] = []
        if result.get("ids") and result["ids"][0]:
            for i in range(len(result["ids"][0])):
                distance = result["distances"][0][i]
                metadata = result["metadatas"][0][i] if result.get("metadatas") else {}
                items.append({
                    "chunk_id": result["ids"][0][i],
                    "text": result["documents"][0][i],
                    "score": round(1.0 / (1.0 + distance), 4),
                    "conversation_id": metadata.get("conversation_id", ""),
                    "role": metadata.get("role", ""),
                    "timestamp": metadata.get("timestamp", ""),
                })
        return items

    def keyword_search(self, query_text: str, top_k: int = 10) -> list[dict]:
        """Substring search via Chroma where_document.

        ponytail: uses native $contains, no BM25, no external index.
        """
        collection = self.client.get_or_create_collection(name="conversations")
        result = collection.get(
            where_document={"$contains": query_text},
            limit=top_k,
            include=["documents", "metadatas"],
        )
        items: list[dict] = []
        if result.get("ids"):
            for i in range(len(result["ids"])):
                metadata = result["metadatas"][i] if result.get("metadatas") else {}
                items.append({
                    "chunk_id": result["ids"][i],
                    "text": result["documents"][i] if result.get("documents") else "",
                    "score": 0.0,
                    "conversation_id": metadata.get("conversation_id", ""),
                    "role": metadata.get("role", ""),
                    "timestamp": metadata.get("timestamp", ""),
                })
        return items

    def get_by_conversation_id(self, conversation_id: str) -> list[dict]:
        collection = self.client.get_or_create_collection(name="conversations")
        result = collection.get(
            where={"conversation_id": conversation_id},
            include=["documents", "metadatas"],
        )
        items: list[dict] = []
        if result.get("ids"):
            for i in range(len(result["ids"])):
                metadata = result["metadatas"][i] if result.get("metadatas") else {}
                items.append({
                    "chunk_id": result["ids"][i],
                    "text": result["documents"][i] if result.get("documents") else "",
                    "role": metadata.get("role", ""),
                    "timestamp": metadata.get("timestamp", ""),
                })
        return items

    def delete_by_conversation_id(self, conversation_id: str) -> int:
        collection = self.client.get_or_create_collection(name="conversations")
        result = collection.get(where={"conversation_id": conversation_id})
        if result.get("ids"):
            collection.delete(ids=result["ids"])
            return len(result["ids"])
        return 0

    def get_all_metadata(self) -> list[dict]:
        """Return all chunks with metadata for stats. ponytail: full scan, fine for personal use."""
        collection = self.client.get_or_create_collection(name="conversations")
        result = collection.get(include=["documents", "metadatas"])
        items: list[dict] = []
        if result.get("ids"):
            for i in range(len(result["ids"])):
                metadata = result["metadatas"][i] if result.get("metadatas") else {}
                items.append({
                    "chunk_id": result["ids"][i],
                    "text": result["documents"][i] if result.get("documents") else "",
                    **metadata,
                })
        return items
