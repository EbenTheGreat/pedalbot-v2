import logging
from dataclasses import dataclass
import time
from typing import List, Dict, Any, Optional, Tuple, Union, Sequence
from voyageai.client import Client
from asyncio import to_thread, sleep



logger = logging.getLogger(__name__)

@dataclass
class EmbeddingResult:
    """Result from embedding operation."""
    embeddings: List[List[float]]
    token_count: int
    cost_usd: float
    latency_ms: int
    model: str

    def __repr__(self) -> str:
        return (
            f"<EmbeddingResult embeddings={len(self.embeddings)} "
            f"tokens={self.token_count} cost=${self.cost_usd:.4f} "
            f"latency={self.latency_ms}ms>"
        )


class EmbeddingService:
    """
    VoyageAI embeddings service with batching and retry logic.
    
    Usage:
        service = EmbeddingsService(
            api_key="sk-...",
            model="voyage-3.5"
        )
        
        result = await service.embed_texts([
            "What is the input impedance?",
            "Boss DS-1 specifications...",
        ])
        
        embeddings = result.embeddings
        cost = result.cost_usd
    """

    PRICING = {
        "voyage-3-lite": 0.12,        # cost per 1M tokens 
        "voyage-3-large": 0.60,
        "voyage-3.5-lite": 0.10,
    }

    DIMENSIONS = {
        "voyage-3.5-lite": 1024
    }

    def __init__(self, api_key: str, model: str= "voyage-3.5-lite",
                batch_size: int= 100, max_retries: int= 3,
                retry_delay: float = 3):
        """
        Initialize embeddings service.
        
        Args:
            api_key: voyageai api key
            model: Embedding model name
            batch_size: Max texts per batch
            max_retries: Max retry attempts on failure
            retry_delay: Initial retry delay in seconds
        """
        self.client= Client(api_key= api_key,
                            max_retries=max_retries,
                            timeout=None
                            )
        self.model= model
        self.batch_size= batch_size
        self.max_retries= max_retries
        self.retry_delay= retry_delay

        # warn if model isn’t in your cost table
        if model not in self.PRICING:
            print(f"""[EmbeddingsService] Warning: unknown model {model},cost tracking may be inaccurate""")

        print(f"EmbeddingsService initialized with VoyageAI model: {model}")

    
    async def embed_texts(
            self,
            texts: List[str],
            show_progress: bool = False
    ) -> EmbeddingResult:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            show_progress: Whether to log progress
        
        Returns:
            EmbeddingResult with embeddings and metadata
        """

        start_time = time.time()
        if not texts:
            raise ValueError("texts list can not be empty")
        
        # Remove texts that are empty or whitespace-only
        valid_texts = [t for t in texts if t.strip()]

        if len(valid_texts) != len(texts):
            logger.warning(f" Filtered out {len(texts) - len(valid_texts)} empty texts")

        if not valid_texts:
            raise ValueError("All texts are empty after filtering")
        
        # Process in batches
        all_embeddings = []
        total_tokens = 0

        for i in range(0, len(valid_texts), self.batch_size):
            # Slice out the current batch of texts  
            # Example: if batch_size = 5 → valid_texts[0:5], then valid_texts[5:10], etc.
            batch = valid_texts[i:i + self.batch_size]

            # Compute current batch number in a human-friendly format (1-based)
            # Example: i = 0 → batch 1, i = 5 → batch 2
            batch_num = i // self.batch_size + 1
            total_batches = (len(valid_texts) + self.batch_size - 1) // self.batch_size

            if show_progress:
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} texts)")

            # Embed batch with retry
            embeddings, tokens = await self._embed_batch_with_retry(batch)

            all_embeddings.extend(embeddings)
            total_tokens += tokens

        # Calculate costs
        cost_per_million = self.PRICING.get(self.model, 0.10)
        cost_usd = (total_tokens / 1_000_000) * cost_per_million

        # Calculate latency
        latency_ms = int((time.time() - start_time) * 1000)

        result = EmbeddingResult(
            embeddings=all_embeddings,
            token_count=total_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            model=self.model
        )

        logger.info(
            f" Generated {len(all_embeddings)} embeddings "
            f"({total_tokens} tokens, ${cost_usd:.4f}, {latency_ms}ms)"
        )

        return result


    async def _embed_batch_with_retry(self, texts: List[str])-> Tuple[Sequence[Sequence[Union[float, int]]], int]:
        """
        Embed a batch of texts with exponential backoff retry.
        
        Returns:
            Tuple of (embeddings, token_count)
        """ 
        for attempt in range(self.max_retries):
            try:
                response = await to_thread(
                    self.client.embed,
                    texts=texts,
                    model=self.model,)
                
                # VoyageAI returns embeddings in a single list
                embeddings = response.embeddings

                # VoyageAI returns total tokens directly
                token_count = response.total_tokens

                return embeddings, token_count
            
            except Exception as e:
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Embedding failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {delay}s..."
                    )
                    await sleep(delay)
                else:
                    logger.error(f"Embedding failed after {self.max_retries} attempts: {e}")
                    raise
        return [], 0
    

    async def embed_single(self, text: str) -> EmbeddingResult:
        """
        Embed a single text string.
        
        Args:
            text: Text string to embed
        
        Returns:
            EmbeddingResult with single embedding
        """
        result = await self.embed_texts([text])
        return result
    

    def get_dimension(self) -> int:
        """
        Get embedding dimension for the current model.
        
        Returns:
            Dimension as int, or None if unknown
        """
        return self.DIMENSIONS.get(self.model, 1024)
    

    async def health_check(self) -> bool:
        """
        Test if embeddings service is working.
        
        Returns:
            True if healthy, False otherwise
        """
        try:
            await self.embed_single("test")
            return True
        except Exception as e:
            logger.error(f"Embeddings health check failed: {e}")
            return False
        

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
async def embed_chunks(service: EmbeddingService, chunks: List[str],
                    batch_size: Optional[int] = 0) -> EmbeddingResult:
    """
    Convenience function to embed chunks.
    
    Args:
        service: EmbeddingsService instance
        chunks: List of text chunks
        batch_size: Override service batch size
    
    Returns:
        EmbeddingResult
    """
    # If a batch_size was provided (non-zero)
    if batch_size:
        # Save the original batch size temporarily
        original_batch_size= service.batch_size
        
        # Override the service batch size with the new one
        service.batch_size = batch_size

        # Call the embedding method with progress display enabled
        # This is where the actual embedding happens
        result = await service.embed_texts(chunks, show_progress=True)

        # Restore the original batch size so the service behaves normally again
        service.batch_size = original_batch_size

        # Return the embedding result
        return result
    
    # If no batch_size override was given, simply embed the chunks using the default batch size
    return await service.embed_texts(chunks, show_progress=True)

def estimate_embedding_cost(num_tokens: int, 
                            model: str="voyage-3.5-lite") -> float:
    """
    Estimate embedding cost before making API call.
    
    Args:
        num_tokens: Number of tokens to embed
        model: Embedding model name
    
    Returns:
        Estimated cost in USD
    """

    cost_per_million = EmbeddingService.PRICING.get(model, 0.10)
    estimated_cost = (num_tokens / 1_000_000) * cost_per_million
    return estimated_cost


def calculate_total_cost(embedding_results: List[EmbeddingResult]) -> float:
    """
    Calculate total cost from multiple EmbeddingResult objects.
    
    Args:
        embedding_results: List of EmbeddingResult objects
    Returns:
        Total cost in USD
    """

    return sum(result.cost_usd for result in embedding_results)

# ============================================================================
# CACHING 
# ============================================================================
class CachedEmbeddingService(EmbeddingService):
    """
    Embeddings service with caching support.
    
    Useful during development in order not to waste API calls
    re-embedding the same text over and over again
    """

    def __init__(self, *args, cache: Optional[Dict[str, List[float]]]= None, **kwargs):
        """
        Initialize the service.

        Args:
            cache: A dictionary mapping text → embedding vector.
            If None is provided, an empty cache is created.
        """

        # Initialize the parent EmbeddingsService
        super().__init__(*args, **kwargs)
        # Use provided cache or create a new one
        self.cache = cache or {}

    async def embed_texts_with_cache(self, texts: List[str], show_progress: bool = False) -> EmbeddingResult:
        """Embed texts with caching support."""

        # Lists to track which texts are cached and which are not
        cached_embeddings = []   # list of tuples: (index_in_original_list, embedding_vector)
        uncached_texts = []      # texts that are not in cache
        uncached_indices = []    # their original positions
        
        # Loop through all incoming texts
        for i, text in enumerate(texts):
            if text in self.cache:
                # If text already in cache, store its embedding + index
                cached_embeddings.append((i, self.cache[text]))

            else:
                # If not cached, add it to uncached list
                uncached_texts.append(text)
                uncached_indices.append(i)

        # If at least one text was found in the cache, log it
        if cached_embeddings:
            logger.info(f"Cache hit: {len(cached_embeddings)}/{len(texts)} embeddings")

        
        # 1. HANDLE UNCACHED TEXTS
        if uncached_texts:
            # Call parent class to embed the uncached texts
            result = await super().embed_texts(uncached_texts, show_progress=True)

            # Store the new embeddings in cache
            for text, embedding in zip(uncached_texts, result.embeddings):
                self.cache[text] = embedding

            # Prepare an empty list to merge both cached + newly created embeddings
            # Merge cached + uncached safely
            merged = {}

            # Insert cached embeddings in their correct positions
            for i, embedding in cached_embeddings:
                merged[i] = embedding
            
            # Insert newly computed embeddings in their correct positions
            for i, embedding in zip(uncached_indices, result.embeddings):
                merged[i] = embedding

            # Build final ordered list (NO None values)
            ordered_embeddings = [merged[i] for i in range(len(texts))]

            # Replace result.embeddings
            result.embeddings = ordered_embeddings
            
            # Return final combined result
            return result
        
        # 2. HANDLE CASE: ALL TEXTS WERE CACHED
        logger.info("All embeddings loaded from cache")

        return EmbeddingResult(
            embeddings=[emb for _, emb in cached_embeddings],
            token_count=0,
            cost_usd=0.0,
            latency_ms=0,
            model=self.model,
        )
        





