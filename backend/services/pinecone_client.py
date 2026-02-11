"""
Pinecone client for vector storage and semantic search.

Handles:
- Index initialization
- Namespace management (one per pedal manual)
- Upsert (chunked for large batches)
- Hybrid search (vector + metadata filters)
"""
from pinecone import Pinecone, ServerlessSpec
from typing import List, Dict, Tuple, Optional, Any, cast
import logging
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Structured search result from Pinecone."""
    chunk_id: str
    text: str
    score: float
    metadata: Dict[str, Any]

    def __repr__(self) -> str:
        return f"<SearchResult score={self.score:.3f} chunk={self.chunk_id[:20]}...>"

class PineconeClient:
    """
    Wrapper for Pinecone operations with retry logic and batching.
    
    Usage:
        client = PineconeClient(api_key="...", index_name="pedalbot-manuals")
        
        # Upsert chunks
        await client.upsert_chunks(
            namespace="boss_ds1_manual",
            chunks=[...],
            embeddings=[...],
            metadata=[...]
        )
        
        # Search
        results = await client.search(
            query_embedding=[...],
            namespace="boss_ds1_manual",
            top_k=5
        )
    """
    def __init__(self, api_key: str, index_name: str, 
                dimension: int=1024, metric: str="cosine",
                cloud: str="aws", region: str= "us-east-1"):
        """
        Initialize Pinecone client.
        
        Args:
            api_key: Pinecone API key
            index_name: Name of the index (e.g., "pedalbot-manuals")
            dimension: Embedding dimension (1024 for text-embedding-3-small)
            metric: Distance metric (cosine)
            cloud: Cloud provider (aws)
            region: Cloud region
        """
        self.pc = Pinecone(api_key=api_key)
        self.index_name= index_name
        self.dimension= dimension
        self.metric= metric
        self.cloud= cloud
        self.region= region

        # Initialize index (create if doesn't exist)
        self._init_index()

        # Get index instance
        self.index = self.pc.Index(index_name)

        logger.info(f"✅ Pinecone client initialized: {index_name}")

    def _init_index(self) -> None:
        """Create index if it doesn't exist."""
        existing_indexes = [idx.name for idx in self.pc.list_indexes()]

        if self.index_name not in existing_indexes:
            logger.info(f"Creating Pinecone index: {self.index_name}")
            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric,
                spec=ServerlessSpec(
                    cloud=self.cloud,
                    region=self.region
                )
            )

            # Wait for index to be ready
        desc = self.pc.describe_index(name=self.index_name)
        ready = getattr(desc.status, "ready", False)

        while not ready:
            time.sleep(1)
            desc = self.pc.describe_index(name=self.index_name)
            ready = getattr(desc.status, "ready", False)

        
        else:
            logger.info(f"Index already exists: {self.index_name}")


    def upsert_chunks(self, namespace: str, 
                    chunks: List[str], 
                    embeddings: List[List[float]], 
                    metadata_list: List[Dict[str, Any]],
                    batch_size: int = 100) -> Dict[str, Any]:
        """
        Upsert text chunks with embeddings and metadata into Pinecone.
        
        Args:
            namespace: Namespace for the pedal manual
            chunks: List of text chunks
            embeddings: Corresponding list of embeddings
            metadata_list: List of metadata dicts (must include 'text' field)
            batch_size: Number of vectors to upsert per batch (Pinecone limit is 1000)

            Returns:
            Dict with upsert stats {"upserted_count": 87}
        """
        if len(chunks) != len(embeddings) != len(metadata_list):
            raise ValueError("Chunks, embeddings, and metadata lists must have the same length.")
        
        total_upserted = 0

        #prepare vectors for upsert
        vectors = []
        for i, (chunk, embedding, metadata) in enumerate(zip(chunks, embeddings, metadata_list)):
            # Ensure text is in metadata (required for retrieval)
            if "text" not in metadata:
                metadata["text"] = chunk

            vector_id = f"{namespace}_chunk_{i}"
            vectors.append({
                "id": vector_id,
                "values": embedding,
                "metadata": metadata
            })

        # Upsert in batches
        for i in range(0, len(vectors), batch_size):
            batch = vectors[i:i+batch_size]
            try:
                self.index.upsert(
                    vectors=batch,
                    namespace=namespace
                )
                total_upserted += len(batch)
                logger.info(f"Upserted batch {i // batch_size + 1}: {len(batch)} vectors to {namespace}")
            
            except Exception as e:
                logger.error(f"Failed to upsert batch {i // batch_size + 1}: {e}")
                raise
        
        logger.info(f"Total upserted to {namespace}: {total_upserted}")
        return {"upserted_count": total_upserted}
    
    def search(
        self,
        query_embedding: List[float],
        namespace: str,
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
    ) -> List[SearchResult]:
        """
        Semantic search in a namespace.
        
        Args:
            query_embedding: Query vector
            namespace: Namespace to search (e.g., "boss_ds1_manual")
            top_k: Number of results to return
            filter_dict: Metadata filters (e.g., {"section": "specifications"})
            include_metadata: Whether to include metadata in results
        
        Returns:
            List of SearchResult objects
        """
        try:
            response: Any = self.index.query(
                vector=query_embedding,
                namespace=namespace,
                top_k=top_k,
                filter=filter_dict,
                include_metadata=include_metadata
            )
            
            results = []
            for match in response.matches:
                results.append(SearchResult(
                    chunk_id=match.id,
                    text=match.metadata.get('text', '') if include_metadata else '',
                    score=match.score,
                    metadata=match.metadata if include_metadata else {}
                ))
            
            if results:
                logger.info(f"Search in {namespace}: {len(results)} results (top score: {results[0].score:.3f})")
            else:
                logger.info(f"Search in {namespace}: No results found")
            return results
            
        except Exception as e:
            logger.error(f"Search failed in {namespace}: {e}")
            raise

    def delete_namespace(self, namespace: str) -> Dict[str, str]:
        """
        Delete all vectors in a namespace (useful for re-ingestion).
        Args:
            namespace: Namespace to delete
        Returns:
            Status dict
        """
        try: 
            self.index.delete(delete_all=True,  namespace=namespace)
            logger.info(f"Deleted Namespace: {namespace}")
            return {"status": "deleted", "namespace": "namespace"}
        except Exception as e:
            logger.error(f"Failed to delete namespace: {namespace}: {e}")
            raise
    
    def get_namespace_stats(self, namespace: str) -> Dict[str, Any]:
        """
        Get stats for a namespace (vector count, dimension, etc.).
        
        Args:
            namespace: Namespace to query
        
        Returns:
            Stats dict
        """
        try: 
            stats = self.index.describe_index_stats()
            namespace_stats = stats.namespaces.get(namespace, {})

            return{
                "namespace": namespace,
                "vector_count": namespace_stats.get("vector_count", 0),
                "dimension": self.dimension,
                "index_fullness": stats.index_fullness
            }
        
        except Exception as e:
            logger.error (f"Failed to get stats for namespace: {namespace}: {e}")
            raise

    def list_namespaces(self) -> List[str]:
        """
        List all namespaces in the index.
        
        Returns:
            List of namespace strings
        """
        try:
            stats = self.index.describe_index_stats()
            namespaces = list(stats.namespaces.keys())
            logger.info(f"Namespaces in index {self.index_name}: {namespaces}")
            return namespaces
        except Exception as e:
            logger.error(f"Failed to list namespaces: {e}")
            raise

    def health_check(self) -> bool:
        """
        Perform a health check on the Pinecone index.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            self.index.describe_index_stats()
            return True
        except Exception as e:
            logger.error(f"Health check failed for index {self.index_name}: {e}")
            return False
        
# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================
def chunk_id_to_metadata(self, chunk_id: str) -> Dict[str, Any]:
    """
    Convert chunk ID back to metadata dict.
    
    Args:
        chunk_id: Chunk ID (e.g., "boss_ds1_manual_chunk_42")
    
    Returns:
        Metadata dict with 'pedal_manual' and 'chunk_index'
    """
    parts = chunk_id.rsplit("_chunk_", 2)
    if len(parts) == 3:
        namespace = parts[0]
        chunk_index = int(parts[2])
        return {
            "namespace": namespace,
            "chunk_index": chunk_index
        }
    return {}

def build_metadata_filter(
        section: Optional[str] = None,
        page_number: Optional[int] = None,
        **kwargs) -> Optional[Dict[str, Any]]:
    """
    Build Pinecone metadata filter.
    
    Args:
        section: Section name (e.g., "specifications")
        page_number: Page number in manual
        **kwargs: Additional metadata filters
    
    Returns:
        Filter dict or None if no filters
    """
    filters = {}

    if section:
        filters["section"] = section

    if page_number is not None:
        filters["page_number"] = page_number

    filters.update(kwargs)

    return filters if filters else None

# ============================================================================
# SINGLETON INSTANCE 
# ============================================================================
_pinecone_client: Optional[PineconeClient] = None

def get_pinecone_client(
        api_key: Optional[str] = None,
        index_name: Optional[str] = None,
        **kwarags
        ) -> PineconeClient:
    """
    Get or create singleton Pinecone client.
    
    Usage:
        from app.services.pinecone_client import get_pinecone_client
        
        client = get_pinecone_client(
            api_key=settings.PINECONE_API_KEY,
            index_name=settings.PINECONE_INDEX_NAME
        )
    """
    global _pinecone_client

    if _pinecone_client is None:
        if not api_key or not index_name:
            raise ValueError("API key and index name must be provided for initial Pinecone client creation.")
        
        _pinecone_client = PineconeClient(
            api_key=api_key,
            index_name=index_name,
            **kwarags
        )

    return _pinecone_client




