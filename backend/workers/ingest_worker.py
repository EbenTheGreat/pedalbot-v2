"""
Ingestion worker for background PDF processing.

Tasks run in Celery workers, not in the web process.
"""

from celery import Task
from datetime import datetime, timedelta, UTC
from typing import Optional
import logging 
import asyncio

from backend.workers.celery_app import BaseTask, app
from backend.config.config import settings


logger = logging.getLogger(__name__)


# HELPER FUNCTIONS
def _extract_manufacturer_from_pdf(chunks, pdf_metadata) -> Optional[str]:
    """
    Extract manufacturer from PDF content (page 1).
    
    Looks for patterns like:
    - "© 2016 Roland Corporation"
    - "Boss GT-1: Guitar Effects Processor"
    - "Line 6 Helix Owner's Manual"
    
    Args:
        chunks: List of PDF chunks (from processor)
        pdf_metadata: PDF metadata dict
        
    Returns:
        Manufacturer name or None
    """
    import re
    
    # Only check first few chunks (page 1 area)
    first_chunks = chunks[:3] if len(chunks) > 3 else chunks
    
    # Combine text from first chunks
    first_page_text = ""
    for chunk in first_chunks:
        if hasattr(chunk, 'page_content'):
            first_page_text += chunk.page_content + " "
        elif isinstance(chunk, dict) and 'text' in chunk:
            first_page_text += chunk['text'] + " "
    
    if not first_page_text:
        return None
    
    # Manufacturer patterns (check in order of specificity)
    patterns = [
        # Copyright notices
        (r'©\s*\d{4}\s*(Boss|Roland)\s*Corporation', lambda m: 'Boss'),
        (r'©\s*\d{4}\s*(Line\s*6)', lambda m: 'Line 6'),
        (r'©\s*\d{4}\s*(Zoom\s*Corporation)', lambda m: 'Zoom'),
        (r'©\s*\d{4}\s*(TC\s*Electronic)', lambda m: 'TC Electronic'),
        (r'©\s*\d{4}\s*(Fractal\s*Audio)', lambda m: 'Fractal Audio'),
        (r'©\s*\d{4}\s*(Kemper)', lambda m: 'Kemper'),
        (r'©\s*\d{4}\s*(Neural\s*DSP)', lambda m: 'Neural DSP'),
        
        # Product headers (e.g., "BOSS GT-1: Guitar Effects")
        (r'\b(BOSS|Boss)\s+[A-Z0-9-]+\s*:', lambda m: 'Boss'),
        (r'\b(Line\s*6)\s+[A-Za-z0-9]+\s*(Owner|User|Manual)', lambda m: 'Line 6'),
        (r'\b(Zoom)\s+[A-Z0-9]+\s*(User|Manual)', lambda m: 'Zoom'),
        (r'\b(TC\s*Electronic)\s+', lambda m: 'TC Electronic'),
        (r'\b(Electro-Harmonix|EHX)\s+', lambda m: 'Electro-Harmonix'),
        (r'\b(MXR)\s+', lambda m: 'MXR'),
        (r'\b(Ibanez)\s+', lambda m: 'Ibanez'),
        (r'\b(DigiTech)\s+', lambda m: 'DigiTech'),
        (r'\b(Strymon)\s+', lambda m: 'Strymon'),
        (r'\b(Fractal\s*Audio)\s+', lambda m: 'Fractal Audio'),
        (r'\b(Kemper)\s+Profiler', lambda m: 'Kemper'),
        (r'\b(Neural\s*DSP)\s+', lambda m: 'Neural DSP'),
        (r'\b(Walrus\s*Audio)\s+', lambda m: 'Walrus Audio'),
        (r'\b(Chase\s*Bliss)\s+', lambda m: 'Chase Bliss'),
        (r'\b(NUX)\s+', lambda m: 'NUX'),
        (r'\b(Hotone)\s+', lambda m: 'Hotone'),
        (r'\b(Mooer)\s+', lambda m: 'Mooer'),
    ]
    
    for pattern, extractor in patterns:
        match = re.search(pattern, first_page_text, re.IGNORECASE)
        if match:
            return extractor(match)
    
    return None


def _compute_canonical_name(pedal_name: str, manufacturer: Optional[str]) -> str:
    """
    Compute canonical product name for market API queries.
    
    This creates a clean, searchable name like "Boss GT-1" from
    potentially messy inputs like "GT-1 eng03 W".
    
    Args:
        pedal_name: Raw pedal name from filename/manual
        manufacturer: Manufacturer name if known
        
    Returns:
        Canonical product name for Reverb/market searches
    """
    import re
    
    # Start with the pedal name
    cleaned = pedal_name
    
    # Remove common filename artifacts
    patterns_to_remove = [
        r'\s+eng\d*',          # eng, eng03, etc
        r'\s+[a-z]{2}\d+$',    # language codes like fr01
        r'\s+w$',              # trailing W
        r'\s+\d+\.\d+',        # version numbers
        r"\s*owner'?s?\s*manual",  # owner's manual
        r'\s*user\s*manual',   # user manual
        r'\s*manual$',         # trailing manual
        r'\s*english$',        # trailing english
        r'\s*\(\d+\)$',        # duplicate markers like (1)
    ]
    
    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Normalize whitespace
    cleaned = ' '.join(cleaned.split()).strip()
    
    # Fix model number formatting (GT1 → GT-1)
    cleaned = re.sub(r'([A-Za-z]+)(\d+)', r'\1-\2', cleaned)
    
    # Remove double hyphens that might result
    cleaned = re.sub(r'-+', '-', cleaned)
    
    # If manufacturer is known and not already in the name, prepend it
    if manufacturer:
        manufacturer_clean = manufacturer.strip()
        if manufacturer_clean.lower() not in cleaned.lower():
            cleaned = f"{manufacturer_clean} {cleaned}"
    
    return cleaned.strip() or pedal_name  # Fallback to original if cleaning fails


# MANUAL INGESTION TASK
@app.task(name="ingest_manual", base=BaseTask, bind=True)
def process_manual_task(self: Task, manual_id: str) -> dict:
    """
    Process a manual in background (PDF → Chunks → Pinecone).
    
    Args:
        manual_id: Manual ID from MongoDB
    
    Returns:
        Result dict with status
    """
    logger.info(f"Starting ingestion for manual: {manual_id}")

    async def runner():
        """
        Inner async runner that handles MongoDB initialization,
        task execution, and error handling in a single async context.
        """
        from backend.db.mongodb import MongoDB
        
        # Initialize MongoDB FIRST - before any task logic
        await MongoDB.connect(
            uri=settings.MONGODB_URI,
            db_name=settings.MONGODB_DB_NAME
        )
        
        try:
            result = await _process_manual_async(self, manual_id)
            return result
        except Exception as e:
            logger.error(f"Ingestion failed for {manual_id}: {e}", exc_info=True)
            
            # Now we can safely update job status since MongoDB is initialized
            await _update_job_status(
                manual_id=manual_id,
                status="failed",
                error=str(e)
            )
            raise
        finally:
            await MongoDB.close()

    try:
        return asyncio.run(runner())
    except Exception as e:
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def _process_manual_async(task: Task, manual_id: str) -> dict:
    """
    Async processing logic.
    
    Note: MongoDB connection is managed by the parent runner() function.
    
    Args:
        task: Celery task instance
        manual_id: Manual ID
    
    Returns:
        Result dict
    """
    from backend.db.mongodb import MongoDB
    from backend.db.models import ManualStatus, dict_to_document, ManualDocument
    from backend.services.pdf_processor import PdfProcessor
    from backend.services.embeddings import EmbeddingService
    from backend.services.pinecone_client import PineconeClient

    db = MongoDB.get_database()

    # Update job: started
    await _update_job_status(manual_id, "in_progress", started_at=datetime.now(UTC))

    # Get Manual
    manual_doc = await db.manuals.find_one({"manual_id": manual_id})

    if not manual_doc:
        raise ValueError(f"Manual {manual_id} not found")
    
    manual = dict_to_document(manual_doc, ManualDocument)

    if not manual.pdf_url:
        raise ValueError(f"Manual {manual_id} has no PDF URL")

    logger.info(f"Processing: {manual.pedal_name}")

    # Construct the full PDF path from filename
    # pdf_url now contains just the filename (e.g., "nux_mg-30_user_manual.pdf")
    # We construct the full path using the environment-aware uploads_path
    import os
    pdf_filename = manual.pdf_url
    
    # Backwards compatibility: if pdf_url is a full path (legacy), extract just the filename
    if "/" in pdf_filename or "\\" in pdf_filename:
        logger.warning(f"Legacy full path detected in pdf_url: {pdf_filename}")
        pdf_filename = os.path.basename(pdf_filename.replace("\\", "/"))
        logger.info(f"Extracted filename: {pdf_filename}")
    
    pdf_path = os.path.join(settings.uploads_path, pdf_filename)
    
    logger.info(f"PDF path resolved to: {pdf_path}")

    # Step 1: Process PDF (30% progress)
    logger.info(f"Initializing PDF processor with OCR threshold: {settings.OCR_QUALITY_THRESHOLD}")
    
    # DIAGNOSTIC: Check raw env vars
    import os
    import json
    
    # Try file-based credentials first (most reliable)
    creds_file_path = os.environ.get("GOOGLE_VISION_CREDENTIALS_PATH")
    logger.info(f"DIAGNOSTIC: GOOGLE_VISION_CREDENTIALS_PATH = {creds_file_path}")
    
    vision_creds_dict = None
    
    # Option 1: File path (most reliable)
    if creds_file_path and os.path.exists(creds_file_path):
        try:
            with open(creds_file_path, 'r') as f:
                vision_creds_dict = json.load(f)
            logger.info(f"Loaded credentials from file: {creds_file_path}")
            logger.info(f"Credentials for project: {vision_creds_dict.get('project_id')}")
        except Exception as e:
            logger.error(f"Failed to load credentials from file: {e}")
    
    # Option 2: Base64-encoded env var
    if not vision_creds_dict:
        raw_creds = os.environ.get("GOOGLE_VISION_CREDENTIALS")
        logger.info(f"DIAGNOSTIC: GOOGLE_VISION_CREDENTIALS env var exists: {raw_creds is not None}")
        if raw_creds:
            logger.info(f"DIAGNOSTIC: GOOGLE_VISION_CREDENTIALS length: {len(raw_creds)} chars")
        vision_creds_dict = settings.google_vision_credentials_dict
        logger.info(f"DIAGNOSTIC: settings.google_vision_credentials_dict returned: {vision_creds_dict is not None}")
    
    if vision_creds_dict:
        logger.info(f"DIAGNOSTIC: Credentials dict has keys: {list(vision_creds_dict.keys())}")
        logger.info(f"Using service account credentials for project: {vision_creds_dict.get('project_id')}")
        processor = PdfProcessor(
            chunk_size=settings.PDF_CHUNK_SIZE,
            chunk_overlap=settings.PDF_CHUNK_OVERLAP,
            google_credentials_json=vision_creds_dict,  # Pass decoded dict
            ocr_quality_threshold=settings.OCR_QUALITY_THRESHOLD
        )
    elif settings.GOOGLE_API_KEY:
        # Fallback to API key
        logger.info("Using Google API Key for Vision API")
        processor = PdfProcessor(
            chunk_size=settings.PDF_CHUNK_SIZE,
            chunk_overlap=settings.PDF_CHUNK_OVERLAP,
            google_api_key=settings.GOOGLE_API_KEY,
            ocr_quality_threshold=settings.OCR_QUALITY_THRESHOLD
        )
    else:
        logger.warning("No Google Vision credentials found - OCR will be disabled!")
        logger.warning(f"DIAGNOSTIC: settings.GOOGLE_VISION_CREDENTIALS is: {settings.GOOGLE_VISION_CREDENTIALS is not None}")
        processor = PdfProcessor(
            chunk_size=settings.PDF_CHUNK_SIZE,
            chunk_overlap=settings.PDF_CHUNK_OVERLAP,
            ocr_quality_threshold=settings.OCR_QUALITY_THRESHOLD
        )
    
    # Log whether Vision client was initialized
    logger.info(f"Google Vision client initialized: {processor.vision_client is not None}")
    
    # ALWAYS use OCR for pedal manuals when Vision is available
    # Pedal manuals often have diagrams with text labels (like connection diagrams)
    # that PyMuPDF can't extract but OCR can
    force_ocr = processor.vision_client is not None
    
    if force_ocr:
        logger.info("Force OCR enabled - pedal manuals often have diagram text that requires OCR")
    else:
        logger.warning("OCR disabled - diagram text may be missed. Consider adding Google Vision credentials.")

    chunks, pdf_metadata = processor.process_pdf(
        pdf_path=pdf_path,
        pedal_name=manual.pedal_name,
        force_ocr=force_ocr  # Force OCR when available
    ) 
    
    # Log OCR diagnostic info
    logger.info(f"PDF metadata: quality_score={pdf_metadata.get('quality_score')}, "
                f"ocr_used={pdf_metadata.get('ocr_used')}, "
                f"ocr_required={pdf_metadata.get('ocr_required')}")
    
    # Extract manufacturer from PDF if not already set (second attempt)
    manufacturer = manual.manufacturer
    if not manufacturer and chunks:
        manufacturer = _extract_manufacturer_from_pdf(chunks, pdf_metadata)
        if manufacturer:
            logger.info(f"Extracted manufacturer from PDF: '{manufacturer}'")
    
    # Compute canonical_name for market queries (e.g., "Boss GT-1" instead of "GT-1 eng03")
    canonical_name = _compute_canonical_name(manual.pedal_name, manufacturer)
    logger.info(f"Canonical name computed: '{manual.pedal_name}' → '{canonical_name}'")
    
    # Update manufacturer and canonical_name in MongoDB
    if manufacturer or canonical_name:
        update_fields = {}
        if manufacturer:
            update_fields["manufacturer"] = manufacturer
        if canonical_name:
            update_fields["canonical_name"] = canonical_name
        
        await db.manuals.update_one(
            {"manual_id": manual_id},
            {"$set": update_fields}
        )
    
    #  GUARD: Empty chunks = terminal failure, NOT retryable
    if not chunks:
        error_msg = (
            f"No extractable text found in PDF for '{manual.pedal_name}'. "
            f"Quality score: {pdf_metadata.get('quality_score', 0)}, "
            f"OCR used: {pdf_metadata.get('ocr_used', False)}, "
            f"OCR required but unavailable: {pdf_metadata.get('ocr_required', False)}. "
            "This PDF may be a scanned image without OCR, or corrupted."
        )
        logger.error(error_msg)
        
        # Mark as FAILED (not retryable)
        await _update_job_status(
            manual_id,
            "failed",
            error=error_msg,
            progress=30.0
        )
        
        # Update manual status to FAILED
        await db.manuals.update_one(
            {"manual_id": manual_id},
            {"$set": {
                "status": "failed",
                "error": error_msg,
                "quality_score": pdf_metadata.get("quality_score"),
                "ocr_required": pdf_metadata.get("ocr_required", False),
                "ocr_used": pdf_metadata.get("ocr_used", False)
            }}
        )
        
        # Return instead of raising - prevents retry
        return {
            "manual_id": manual_id,
            "pedal_name": manual.pedal_name,
            "status": "failed",
            "error": error_msg
        }
    
    await _update_job_status(
        manual_id,
        "in_progress",
        progress=30.0,
        total_chunks=len(chunks)
    )

    logger.info(f"Extracted {len(chunks)} chunks")

    # Step 2: Generate embeddings (60% progress)
    embedding_service = EmbeddingService(
        api_key=settings.VOYAGEAI_API_KEY,
        model=settings.VOYAGEAI_EMBEDDING_MODEL
    )

    chunk_texts = processor.get_chunk_texts(chunks)

    embedding_result = await embedding_service.embed_texts(
        chunk_texts,
        show_progress=True
    )

    await _update_job_status(manual_id, "in_progress", progress=60.0)
    
    logger.info(f"Generated embeddings: {embedding_result.token_count}tokens, ${embedding_result.cost_usd:.4f}")
    
    # Step 3: Upsert to Pinecone (90% progress)
    pinecone_client = PineconeClient(
        api_key=settings.PINECONE_API_KEY,
        index_name=settings.PINECONE_INDEX_NAME
    )

    chunk_metadata = processor.get_chunk_metadata(chunks)

    upsert_result = pinecone_client.upsert_chunks(
        namespace=manual.pinecone_namespace,
        chunks=chunk_texts,
        embeddings=embedding_result.embeddings,
        metadata_list=chunk_metadata
    )

    await _update_job_status(manual_id, "in_progress", progress=90.0)

    logger.info(f"Upserted {upsert_result['upserted_count']} vectors")

    # Step 4: Update manual status (100% progress)
    await db.manuals.update_one(
        {"manual_id": manual_id},
        {"$set": {
            "status": ManualStatus.COMPLETED.value,
            "chunk_count": len(chunks),
            "page_count": pdf_metadata["page_count"],
            "indexed_at": datetime.now(UTC),
            "quality_score": pdf_metadata.get("quality_score"),
            "ocr_required": pdf_metadata.get("ocr_required", False),
            "ocr_used": pdf_metadata.get("ocr_used", False)
        }}
    )

    # Complete job
    await _update_job_status(
        manual_id,
        "completed",
        progress=100.0,
        chunks_processed=len(chunks),
        completed_at=datetime.utcnow()
    )

    logger.info(f"Ingestion completed: {manual.pedal_name}")
    
    return {
        "manual_id": manual_id,
        "pedal_name": manual.pedal_name,
        "chunks": len(chunks),
        "tokens": embedding_result.token_count,
        "cost_usd": embedding_result.cost_usd,
        "status": "completed"
    }


async def _update_job_status(manual_id: str,
                            status: str,
                            progress: float = 0.0,
                            error: Optional[str] = None,
                            **kwargs) -> None:
    """Update job status in MongoDB.""" 
    from backend.db.mongodb import MongoDB

    db = MongoDB.get_database()

    update_data = {
        "status": status,
        "progress": progress
    }

    if error:
        update_data["error"] = error

    update_data.update(kwargs)

    await db.ingestion_jobs.update_one(
        {"manual_id": manual_id},
        {"$set": update_data}
    )


# CLEANUP TASK
@app.task(name="cleanup_old_jobs", base= BaseTask)
def cleanup_old_jobs_task() -> dict:
    """
    Clean up old completed/failed jobs from MongoDB.
    
    Keeps jobs for 30 days.
    
    Returns:
        Cleanup stats
    """

    logger.info("Cleaning up old jobs")

    result = asyncio.run(_cleanup_old_jobs_async())

    logger.info(f"Cleaned up {result['deleted']} old jobs")

    return result

async def _cleanup_old_jobs_async() -> dict:
    """Async cleanup logic."""
    from backend.db.mongodb import MongoDB

    await MongoDB.connect(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME
    )

    db= MongoDB.get_database()

    try:
        # Delete jobs older than 30 days
        cut_off_date = datetime.now(UTC) - timedelta(days=30)

        result = await db.ingestion_jobs.delete_many(
            {
            "created_at": {"$lt": cut_off_date},
            "status": {"$in": ["completed", "failed"]}
            }
        
        )

        return {
            "deleted": result.deleted_count,
            "cutoff_date": cut_off_date.isoformat()
        }
        
    finally:
        await MongoDB.close()


# BATCH INGESTION TASK
@app.task(name='batch_ingest_manuals', base=BaseTask)
def batch_ingest_manuals_task(manual_ids: list[str]) -> dict:
    """
    Ingest multiple manuals in parallel.
    
    Args:
        manual_ids: List of manual IDs
    
    Returns:
        Batch results
    """
    from celery import group, signature
    
    logger.info(f"Starting batch ingestion: {len(manual_ids)} manuals")
    
    # Create parallel tasks
    job = group(
        signature("ingest_manual", args=(manual_id,))
        for manual_id in manual_ids
    )
    
    # Execute
    result = job.apply_async()
    
    # Wait for all tasks
    results = result.get(timeout=3600)  # 1 hour timeout
    
    # Aggregate stats
    completed = sum(1 for r in results if r.get("status") == "completed")
    failed = len(results) - completed
    
    return {
        "total": len(manual_ids),
        "completed": completed,
        "failed": failed,
        "results": results
    }









