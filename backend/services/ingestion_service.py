"""
Ingestion service for processing PDFs inline (no Celery required).

This module extracts the core processing logic from the Celery worker
so it can run within the FastAPI process using BackgroundTasks.
"""

from datetime import datetime, UTC
from typing import Optional
import logging
import os
import json

from backend.config.config import settings

logger = logging.getLogger(__name__)


# HELPER FUNCTIONS (moved from ingest_worker.py)

def _extract_manufacturer_from_pdf(chunks, pdf_metadata) -> Optional[str]:
    """Extract manufacturer from PDF content (page 1)."""
    import re

    first_chunks = chunks[:3] if len(chunks) > 3 else chunks
    first_page_text = ""
    for chunk in first_chunks:
        if hasattr(chunk, 'page_content'):
            first_page_text += chunk.page_content + " "
        elif isinstance(chunk, dict) and 'text' in chunk:
            first_page_text += chunk['text'] + " "

    if not first_page_text:
        return None

    patterns = [
        (r'©\s*\d{4}\s*(Boss|Roland)\s*Corporation', lambda m: 'Boss'),
        (r'©\s*\d{4}\s*(Line\s*6)', lambda m: 'Line 6'),
        (r'©\s*\d{4}\s*(Zoom\s*Corporation)', lambda m: 'Zoom'),
        (r'©\s*\d{4}\s*(TC\s*Electronic)', lambda m: 'TC Electronic'),
        (r'©\s*\d{4}\s*(Fractal\s*Audio)', lambda m: 'Fractal Audio'),
        (r'©\s*\d{4}\s*(Kemper)', lambda m: 'Kemper'),
        (r'©\s*\d{4}\s*(Neural\s*DSP)', lambda m: 'Neural DSP'),
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
        match = __import__('re').search(pattern, first_page_text, __import__('re').IGNORECASE)
        if match:
            return extractor(match)

    return None


def _compute_canonical_name(pedal_name: str, manufacturer: Optional[str]) -> str:
    """Compute canonical product name for market API queries."""
    import re

    cleaned = pedal_name
    patterns_to_remove = [
        r'\s+eng\d*',
        r'\s+[a-z]{2}\d+$',
        r'\s+w$',
        r'\s+\d+\.\d+',
        r"\s*owner'?s?\s*manual",
        r'\s*user\s*manual',
        r'\s*manual$',
        r'\s*english$',
        r'\s*\(\d+\)$',
    ]

    for pattern in patterns_to_remove:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)

    cleaned = ' '.join(cleaned.split()).strip()
    cleaned = re.sub(r'([A-Za-z]+)(\d+)', r'\1-\2', cleaned)
    cleaned = re.sub(r'-+', '-', cleaned)

    if manufacturer:
        manufacturer_clean = manufacturer.strip()
        if manufacturer_clean.lower() not in cleaned.lower():
            cleaned = f"{manufacturer_clean} {cleaned}"

    return cleaned.strip() or pedal_name


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


async def process_manual_inline(manual_id: str) -> dict:
    """
    Process a manual inline (PDF → Chunks → Pinecone).

    This is the same logic as the Celery worker but runs directly
    in the FastAPI process via BackgroundTasks.

    Args:
        manual_id: Manual ID from MongoDB

    Returns:
        Result dict with status
    """
    from backend.db.mongodb import MongoDB
    from backend.db.models import ManualStatus, dict_to_document, ManualDocument
    from backend.services.pdf_processor import PdfProcessor
    from backend.services.embeddings import EmbeddingService
    from backend.services.pinecone_client import PineconeClient

    logger.info(f"Starting inline ingestion for manual: {manual_id}")

    try:
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

        # Resolve PDF path
        pdf_filename = manual.pdf_url
        if "/" in pdf_filename or "\\" in pdf_filename:
            logger.warning(f"Legacy full path detected in pdf_url: {pdf_filename}")
            pdf_filename = os.path.basename(pdf_filename.replace("\\", "/"))

        pdf_path = os.path.join(settings.uploads_path, pdf_filename)
        logger.info(f"PDF path resolved to: {pdf_path}")

        # Step 1: Process PDF (30% progress)
        # Try file-based credentials first
        creds_file_path = os.environ.get("GOOGLE_VISION_CREDENTIALS_PATH")
        vision_creds_dict = None

        if creds_file_path and os.path.exists(creds_file_path):
            try:
                with open(creds_file_path, 'r') as f:
                    vision_creds_dict = json.load(f)
                logger.info(f"Loaded credentials from file: {creds_file_path}")
            except Exception as e:
                logger.error(f"Failed to load credentials from file: {e}")

        if not vision_creds_dict:
            vision_creds_dict = settings.google_vision_credentials_dict

        if vision_creds_dict:
            processor = PdfProcessor(
                chunk_size=settings.PDF_CHUNK_SIZE,
                chunk_overlap=settings.PDF_CHUNK_OVERLAP,
                google_credentials_json=vision_creds_dict,
                ocr_quality_threshold=settings.OCR_QUALITY_THRESHOLD
            )
        elif settings.GOOGLE_API_KEY:
            processor = PdfProcessor(
                chunk_size=settings.PDF_CHUNK_SIZE,
                chunk_overlap=settings.PDF_CHUNK_OVERLAP,
                google_api_key=settings.GOOGLE_API_KEY,
                ocr_quality_threshold=settings.OCR_QUALITY_THRESHOLD
            )
        else:
            logger.warning("No Google Vision credentials found - OCR disabled!")
            processor = PdfProcessor(
                chunk_size=settings.PDF_CHUNK_SIZE,
                chunk_overlap=settings.PDF_CHUNK_OVERLAP,
                ocr_quality_threshold=settings.OCR_QUALITY_THRESHOLD
            )

        force_ocr = processor.vision_client is not None

        chunks, pdf_metadata = processor.process_pdf(
            pdf_path=pdf_path,
            pedal_name=manual.pedal_name,
            force_ocr=force_ocr
        )

        # Extract manufacturer from PDF
        manufacturer = manual.manufacturer
        if not manufacturer and chunks:
            manufacturer = _extract_manufacturer_from_pdf(chunks, pdf_metadata)
            if manufacturer:
                logger.info(f"Extracted manufacturer from PDF: '{manufacturer}'")

        # Compute canonical name
        canonical_name = _compute_canonical_name(manual.pedal_name, manufacturer)
        logger.info(f"Canonical name: '{manual.pedal_name}' → '{canonical_name}'")

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

        # Guard: Empty chunks
        if not chunks:
            error_msg = (
                f"No extractable text found in PDF for '{manual.pedal_name}'. "
                f"Quality score: {pdf_metadata.get('quality_score', 0)}, "
                f"OCR used: {pdf_metadata.get('ocr_used', False)}."
            )
            logger.error(error_msg)
            await _update_job_status(manual_id, "failed", error=error_msg, progress=30.0)
            await db.manuals.update_one(
                {"manual_id": manual_id},
                {"$set": {"status": "failed", "error": error_msg}}
            )
            return {"manual_id": manual_id, "status": "failed", "error": error_msg}

        await _update_job_status(manual_id, "in_progress", progress=30.0, total_chunks=len(chunks))
        logger.info(f"Extracted {len(chunks)} chunks")

        # Step 2: Generate embeddings (60% progress)
        embedding_service = EmbeddingService(
            api_key=settings.VOYAGEAI_API_KEY,
            model=settings.VOYAGEAI_EMBEDDING_MODEL
        )
        chunk_texts = processor.get_chunk_texts(chunks)
        embedding_result = await embedding_service.embed_texts(chunk_texts, show_progress=True)
        await _update_job_status(manual_id, "in_progress", progress=60.0)
        logger.info(f"Generated embeddings: {embedding_result.token_count} tokens, ${embedding_result.cost_usd:.4f}")

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

        # Step 4: Update manual status (100%)
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

        await _update_job_status(
            manual_id, "completed",
            progress=100.0,
            chunks_processed=len(chunks),
            completed_at=datetime.now(UTC)
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

    except Exception as e:
        logger.error(f"Ingestion failed for {manual_id}: {e}", exc_info=True)
        try:
            await _update_job_status(manual_id=manual_id, status="failed", error=str(e))
            db = MongoDB.get_database()
            await db.manuals.update_one(
                {"manual_id": manual_id},
                {"$set": {"status": "failed", "error": str(e)}}
            )
        except Exception:
            logger.error("Failed to update job status after error", exc_info=True)
        raise
