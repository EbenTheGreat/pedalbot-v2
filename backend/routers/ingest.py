"""
FastAPI router for manual ingestion endpoints.

Endpoints:
- POST /api/v1/ingest/upload - Upload PDF and create manual record
- POST /api/v1/ingest/process - Process uploaded manual (trigger background job)
- GET /api/v1/ingest/status/{manual_id} - Check ingestion status
- DELETE /api/v1/ingest/{manual_id} - Delete manual and vectors
"""

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, BackgroundTasks
from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Dict, Any, Optional
import logging
from datetime import datetime
from pydantic import BaseModel, Field
from backend.db.mongodb import get_database
from backend.db.models import (
    ManualDocument,
    ManualStatus,
    IngestionJobDocument,
    JobStatus,
    document_to_dict,
    dict_to_document,
)

from backend.services.ingestion_service import process_manual_inline


from backend.services.pdf_processor import PdfProcessor, validate_pdf, get_pdf_file_size
from backend.services.embeddings import EmbeddingService
from backend.services.pinecone_client import PineconeClient
from backend.config.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ingest", tags=["ingestion"])


# REQUEST/RESPONSE MODELS
class UploadManualRequest(BaseModel):
    """Request to upload a manual."""
    pedal_name: str= Field(..., description="Name of the pedal (e.g., 'Boss DS-1')")
    manufacturer: Optional[str]= Field(None, description="Manufacturer name")
    pdf_url: Optional[str]= Field(None, description="Public PDF URL (if not uploading)")


class UploadManualResponse(BaseModel):
    """Response after uploading manual."""
    manual_id: str
    pedal_name: str
    pinecone_namespace: str
    status: str
    message: str


class ProcessManualRequest(BaseModel):
    """Request to process a manual."""
    manual_id: str


class ProcessManualResponse(BaseModel):
    """Response after triggering processing."""
    job_id: str
    manual_id: str
    status: str
    message: str

class IngestionStatusResponse(BaseModel):
    """status of ingestion job"""
    manual_id: str
    status: str
    progress: float
    chunks_processed: int
    total_cunks: Optional[int]
    error: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class ManualListItem(BaseModel):
    """Summary of a manual for list view"""
    manual_id: str
    pedal_name: str
    manufacturer: Optional[str]
    status: str
    chunk_count: int
    file_size_bytes: Optional[int]
    uploaded_at: datetime
    indexed_at: Optional[datetime]


class ListManualsResponse(BaseModel):
    """Response for listing all manuals"""
    manuals: list[ManualListItem]
    total: int


# HELPER FUNCTIONS
def _extract_manufacturer_from_filename(filename: str) -> Optional[str]:
    """
    Extract manufacturer from filename patterns.
    
    Examples:
    - "boss_gt1_manual.pdf" → "Boss"
    - "line6_helix_manual.pdf" → "Line 6"
    - "GT-1_eng03_W.pdf" → None (no manufacturer in filename)
    
    Args:
        filename: PDF filename
        
    Returns:
        Manufacturer name or None
    """
    import re
    
    # Common manufacturer patterns (case-insensitive)
    # Format: (pattern, canonical_name)
    manufacturers = [
        (r'\b(boss)\b', 'Boss'),
        (r'\b(line\s?6|line6)\b', 'Line 6'),
        (r'\b(zoom)\b', 'Zoom'),
        (r'\b(tc\s?electronic|tcelectronic)\b', 'TC Electronic'),
        (r'\b(electro[\s-]?harmonix|ehx)\b', 'Electro-Harmonix'),
        (r'\b(mxr)\b', 'MXR'),
        (r'\b(ibanez)\b', 'Ibanez'),
        (r'\b(digitech)\b', 'DigiTech'),
        (r'\b(strymon)\b', 'Strymon'),
        (r'\b(fractal\s?audio|fractal)\b', 'Fractal Audio'),
        (r'\b(kemper)\b', 'Kemper'),
        (r'\b(neural\s?dsp|neuraldsp)\b', 'Neural DSP'),
        (r'\b(walrus\s?audio|walrus)\b', 'Walrus Audio'),
        (r'\b(chase\s?bliss|chasebliss)\b', 'Chase Bliss'),
        (r'\b(roland)\b', 'Roland'),
        (r'\b(fender)\b', 'Fender'),
        (r'\b(vox)\b', 'Vox'),
        (r'\b(nux)\b', 'NUX'),
        (r'\b(hotone)\b', 'Hotone'),
        (r'\b(mooer)\b', 'Mooer'),
    ]
    
    filename_lower = filename.lower()
    
    for pattern, canonical_name in manufacturers:
        if re.search(pattern, filename_lower):
            return canonical_name
    
    return None


# Known products mapping: model number → (manufacturer, canonical name)
# This helps resolve filenames without manufacturer prefixes (e.g., "GT-1_eng03_W.pdf")
KNOWN_PRODUCTS = {
    # Boss products
    'gt-1': ('Boss', 'Boss GT-1'),
    'gt1': ('Boss', 'Boss GT-1'),
    'gt-10': ('Boss', 'Boss GT-10'),
    'gt-100': ('Boss', 'Boss GT-100'),
    'gt-1000': ('Boss', 'Boss GT-1000'),
    'ds-1': ('Boss', 'Boss DS-1'),
    'ds1': ('Boss', 'Boss DS-1'),
    'me-80': ('Boss', 'Boss ME-80'),
    'me-50': ('Boss', 'Boss ME-50'),
    'rc-3': ('Boss', 'Boss RC-3'),
    'rc-30': ('Boss', 'Boss RC-30'),
    'katana': ('Boss', 'Boss Katana'),
    
    # Line 6 products
    'helix': ('Line 6', 'Line 6 Helix'),
    'hx stomp': ('Line 6', 'Line 6 HX Stomp'),
    'hx effects': ('Line 6', 'Line 6 HX Effects'),
    'pod go': ('Line 6', 'Line 6 POD Go'),
    'pod hd500': ('Line 6', 'Line 6 POD HD500'),
    
    # NUX products
    'mg-30': ('NUX', 'NUX MG-30'),
    'mg30': ('NUX', 'NUX MG-30'),
    'mg-300': ('NUX', 'NUX MG-300'),
    
    # Zoom products
    'g3': ('Zoom', 'Zoom G3'),
    'g3n': ('Zoom', 'Zoom G3n'),
    'g5': ('Zoom', 'Zoom G5'),
    'g5n': ('Zoom', 'Zoom G5n'),
    'ms-70cdr': ('Zoom', 'Zoom MS-70CDR'),
    
    # Ibanez products
    'ts9': ('Ibanez', 'Ibanez TS9'),
    'ts-9': ('Ibanez', 'Ibanez TS9'),
    'tube screamer': ('Ibanez', 'Ibanez Tube Screamer'),
    
    # Strymon products
    'timeline': ('Strymon', 'Strymon Timeline'),
    'bigsky': ('Strymon', 'Strymon BigSky'),
    'mobius': ('Strymon', 'Strymon Mobius'),
}


def _extract_pedal_name_from_filename(filename: str) -> str:
    """
    Extract a clean pedal name from messy filenames.
    
    Uses 3-layer extraction:
    1. Path/URL stripping - Remove filesystem and URL path components
    2. Model number extraction - Find pedal model patterns (XX-NN)
    3. Manufacturer detection - Look up or extract manufacturer name
    
    Examples:
    - "Home Httpd Data MEDIA-DATA 2 Nux MG-30 ENGLISH-.pdf" → "NUX MG-30"
    - "Downloads_Boss_GT-1_manual_v2.pdf" → "Boss GT-1"
    - "helix_3.80_owner's_manual___english.pdf" → "Line 6 Helix"
    - "www_example_com_strymon_timeline.pdf" → "Strymon Timeline"
    
    Args:
        filename: PDF filename (may contain path fragments)
        
    Returns:
        Cleaned pedal name with manufacturer prefix
    """
    import re
    
    logger.info(f"[PEDAL_EXTRACT] Input filename: '{filename}'")
    
    # Remove .pdf extension and lowercase
    name = filename.lower().replace(".pdf", "")
    
    # =================================================================
    # LAYER 0: EARLY MODEL NUMBER EXTRACTION (before any splitting)
    # Find model patterns while hyphens are still intact
    # =================================================================
    
    # Model number patterns to find FIRST (before splitting)
    # Use (?:^|[_\s]) instead of \b because \b doesn't work with underscores
    # Order matters: more specific patterns first
    early_model_patterns = [
        r'(?:^|[_\s])([a-z]{2})[-]?(\d{2,3})([a-z]{2,3})(?:[_\s]|$)',   # MS-70CDR
        r'(?:^|[_\s])([a-z]{1,3})[-](\d{1,4})([a-z]?)(?:[_\s]|$)',      # GT-1, MG-30 (WITH hyphen)
        r'(?:^|[_\s])([a-z]{2})(\d{1,4})([a-z]?)(?:[_\s]|$)',            # DS1, G3n (NO hyphen)
    ]
    
    found_model = None
    for pattern in early_model_patterns:
        matches = re.findall(pattern, name, re.IGNORECASE)
        for match in matches:
            if len(match) >= 2:
                prefix, num = match[0], match[1]
                # Skip if this looks like a version (preceded by a dot like "3.80")
                version_check = rf'\d\.{re.escape(num)}'
                if re.search(version_check, name):
                    continue
                # Skip if prefix is a language code
                if prefix.lower() in {'eng', 'en', 'fr', 'de', 'jp', 'es'}:
                    continue
                # Skip "w" suffix patterns that are just trailing markers
                if prefix.lower() == 'w' and len(num) <= 2:
                    continue
                # Build the model number
                suffix = match[2] if len(match) > 2 else ''
                found_model = f"{prefix.upper()}-{num}{suffix}"
                logger.debug(f"[PEDAL_EXTRACT] Early model extraction: {found_model}")
                break
        if found_model:
            break
    
    # =================================================================
    # LAYER 1: PATH/URL STRIPPING
    # Remove common filesystem and URL path components
    # =================================================================
    
    # Words that are commonly part of file paths or URLs (not pedal names)
    path_words = {
        # Filesystem paths
        'home', 'users', 'user', 'downloads', 'download', 'documents', 'document',
        'desktop', 'tmp', 'temp', 'var', 'www', 'public', 'private', 'shared',
        'httpd', 'data', 'media', 'files', 'file', 'uploads', 'upload',
        'content', 'assets', 'static', 'resources', 'library', 'libraries',
        # URL components
        'http', 'https', 'www', 'com', 'org', 'net', 'io', 'co', 'uk',
        # Common noise words
        'manual', 'manuals', 'pdf', 'pdfs', 'docs', 'doc', 'guide', 'guides',
        'english', 'eng', 'en', 'fr', 'jp', 'es',
        # Generic words
        'the', 'a', 'an', 'of', 'for', 'with', 'and', 'or',
        'owner', 'owners', 'user', 'users', 'v', 'version', 'rev', 'final',
    }
    
    # Replace separators with spaces (but NOT hyphens in model numbers)
    name_for_words = name.replace('_', ' ').replace('.', ' ')
    # Also split on hyphens, but we already extracted model numbers above
    name_for_words = name_for_words.replace('-', ' ')
    
    # Split into words and filter
    words = name_for_words.split()
    filtered_words = []
    for word in words:
        word_clean = word.strip()
        if not word_clean:
            continue
        if word_clean in path_words:
            continue
        # Skip standalone numbers
        if re.match(r'^\d+$', word_clean):
            continue
        # Skip very short words (1 char)
        if len(word_clean) <= 1:
            continue
        # Skip numeric-only words that look like version suffixes (e.g., "03", "80")
        if re.match(r'^\d{2,3}$', word_clean):
            continue
        filtered_words.append(word_clean)
    
    logger.debug(f"[PEDAL_EXTRACT] After filtering: {filtered_words}")
    
    # =================================================================
    # LAYER 2: CHECK KNOWN PRODUCTS
    # =================================================================
    
    # Check if the found model matches a known product
    if found_model:
        model_key = found_model.lower().replace('-', '')  # e.g., "mg30"
        model_key_hyphen = found_model.lower()  # e.g., "mg-30"
        
        for key in [model_key, model_key_hyphen]:
            if key in KNOWN_PRODUCTS:
                manufacturer, canonical = KNOWN_PRODUCTS[key]
                logger.info(f"[PEDAL_EXTRACT] Known product via model: '{filename}' → '{canonical}'")
                return canonical
    
    # Also check filtered words against known products
    for word in filtered_words:
        if word in KNOWN_PRODUCTS:
            manufacturer, canonical = KNOWN_PRODUCTS[word]
            logger.info(f"[PEDAL_EXTRACT] Known product via word: '{filename}' → '{canonical}'")
            return canonical
    
    # =================================================================
    # LAYER 3: MANUFACTURER DETECTION
    # =================================================================
    
    manufacturer_keywords = {
        'boss': 'Boss',
        'line6': 'Line 6',
        'line': 'Line 6',
        'zoom': 'Zoom',
        'nux': 'NUX',
        'ibanez': 'Ibanez',
        'mxr': 'MXR',
        'strymon': 'Strymon',
        'tc': 'TC Electronic',
        'electro': 'Electro-Harmonix',
        'ehx': 'Electro-Harmonix',
        'digitech': 'DigiTech',
        'fractal': 'Fractal Audio',
        'kemper': 'Kemper',
        'neural': 'Neural DSP',
        'walrus': 'Walrus Audio',
        'chase': 'Chase Bliss',
        'roland': 'Roland',
        'fender': 'Fender',
        'vox': 'Vox',
        'hotone': 'Hotone',
        'mooer': 'Mooer',
    }
    
    # Product names that imply a manufacturer
    product_to_manufacturer = {
        'helix': 'Line 6',
        'katana': 'Boss',
        'timeline': 'Strymon',
        'bigsky': 'Strymon',
        'mobius': 'Strymon',
        'flint': 'Strymon',
    }
    
    found_manufacturer = None
    found_product_name = None
    
    for word in filtered_words:
        if word in manufacturer_keywords:
            found_manufacturer = manufacturer_keywords[word]
            break
        if word in product_to_manufacturer:
            found_manufacturer = product_to_manufacturer[word]
            found_product_name = word.title()
            break
    
    # =================================================================
    # FINAL ASSEMBLY
    # =================================================================
    
    # If we found a product name (like "helix")
    if found_product_name:
        canonical = f"{found_manufacturer} {found_product_name}"
        logger.info(f"[PEDAL_EXTRACT] Product name: '{filename}' → '{canonical}'")
        return canonical
    
    # If we have manufacturer and model
    if found_manufacturer and found_model:
        canonical = f"{found_manufacturer} {found_model}"
        logger.info(f"[PEDAL_EXTRACT] Constructed: '{filename}' → '{canonical}'")
        return canonical
    
    # If we only have model, try to look it up
    if found_model:
        # Try various formats against KNOWN_PRODUCTS
        model_variants = [
            found_model.lower().replace('-', ''),
            found_model.lower(),
        ]
        for variant in model_variants:
            if variant in KNOWN_PRODUCTS:
                manufacturer, canonical = KNOWN_PRODUCTS[variant]
                logger.info(f"[PEDAL_EXTRACT] Model lookup: '{filename}' → '{canonical}'")
                return canonical
        
        # If no manufacturer found, just return the model
        logger.info(f"[PEDAL_EXTRACT] Model only: '{filename}' → '{found_model}'")
        return found_model
    
    # Fallback: format remaining words nicely
    if filtered_words:
        result_words = []
        for word in filtered_words:
            if re.match(r'^[a-z]+\d+[a-z]*$', word, re.IGNORECASE):
                # Model number pattern
                formatted = re.sub(r'([a-zA-Z]+)(\d+)', r'\1-\2', word.upper())
                result_words.append(formatted)
            elif re.match(r'^[a-z]+$', word):
                result_words.append(word.title())
            else:
                result_words.append(word.upper())
        
        result = ' '.join(result_words)
        logger.info(f"[PEDAL_EXTRACT] Fallback: '{filename}' → '{result}'")
        return result
    
    logger.warning(f"[PEDAL_EXTRACT] No name extracted: '{filename}'")
    return "Unknown Pedal"


# ENDPOINTS
@router.post("/upload", response_model=UploadManualResponse)
async def upload_manual(
    pdf_file: UploadFile = File(..., description="PDF manual file"),
    db: AsyncIOMotorDatabase = Depends(get_database),
    background_tasks: BackgroundTasks = None,
):
    """
    Upload a pedal manual PDF.
    
    The pedal name is extracted from the filename.
    Example: "Boss_DS-1_manual.pdf" → pedal_name: "Boss DS-1"
    """
    try:
        # Validate file type
        filename = pdf_file.filename
        if not filename or not filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="File must be a PDF")

        # Extract pedal name from filename (smarter extraction)
        pedal_name = _extract_pedal_name_from_filename(filename)
        
        # Generate namespace (will be manual_<uuid> in the worker)
        namespace = f"manual_{pedal_name.lower().replace(' ', '_').replace('-', '_')}"
        
        # Check if manual already exists
        existing = await db.manuals.find_one({"pedal_name": pedal_name})
        if existing:
            raise HTTPException(
                status_code=409,
                detail=f"Manual for '{pedal_name}' already exists (manual_id: {existing['manual_id']})"
            )
        
        # Read file content
        content = await pdf_file.read()
        file_size = len(content)
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024

        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {settings.MAX_UPLOAD_SIZE_MB}MB"
            )
        
        # Save file to uploads_dir
        import os
        import aiofiles
        from pathlib import Path
        
        # Use settings.uploads_path for environment-aware path resolution
        uploads_dir = settings.uploads_path
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save file locally with full path for this process
        local_pdf_path = os.path.join(uploads_dir, filename)
        
        async with aiofiles.open(local_pdf_path, 'wb') as f:
            await f.write(content)
        
        logger.info(f"Uploaded PDF: {filename} ({file_size} bytes) to {local_pdf_path}")
        
        # IMPORTANT: Store only the filename in MongoDB, not full path!
        
        # Extract manufacturer from filename (first attempt)
        manufacturer = _extract_manufacturer_from_filename(filename)
        if manufacturer:
            logger.info(f"Extracted manufacturer from filename: '{manufacturer}'")
        
        # Create manual document
        manual = ManualDocument(
            pedal_name=pedal_name,
            manufacturer=manufacturer,
            pdf_url=filename,  # Store ONLY filename, not full path
            pinecone_namespace=namespace,
            status=ManualStatus.PENDING,
            file_size_bytes=file_size,
        )

        # Insert to MongoDB
        await db.manuals.insert_one(document_to_dict(manual))

        # Trigger inline background processing (no Celery/Redis needed)
        background_tasks.add_task(process_manual_inline, manual.manual_id)

        logger.info(f"Manual created and processing started: {manual.manual_id} ({pedal_name})")

        return UploadManualResponse(
            manual_id=manual.manual_id,
            pedal_name=pedal_name,
            pinecone_namespace=namespace,
            status="processing",
            message=f" Manual uploaded and auto-ingestion started! Check /status/{manual.manual_id} for progress."
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    

@router.post("/process", response_model=ProcessManualResponse)
async def process_manual(manual_id: str,
                        db: AsyncIOMotorDatabase= Depends(get_database),
                        background_tasks: BackgroundTasks = None):
    """
    Start processing a manual (PDF → chunks → Pinecone).
    
    This triggers a background task that:
    1. Extracts text from PDF
    2. Chunks the text
    3. Generates embeddings
    4. Upserts to Pinecone
    """
    # Get Manual
    manual_doc = await db.manuals.find_one({"manual_id": manual_id})
    
    if not manual_doc:
        raise HTTPException(status_code=404, detail= f" Manual: {manual_id} not found")
    
    manual = dict_to_document(manual_doc, ManualDocument)

    # Check Status
    if manual.status == ManualStatus.PROCESSING.value:
        raise HTTPException(status_code=409, detail="Manual is already being processed")
    
    if manual.status == ManualStatus.COMPLETED:
        raise HTTPException(status_code=409, detail="Manual already processed")
    
    # Create Ingestion Job
    job = IngestionJobDocument(manual_id=manual_id)
    await db.ingestion_jobs.insert_one(document_to_dict(job))

    # Update Manual Status
    await db.manuals.update_one(
        {"manual_id": manual_id},
        {"$set": {"status": ManualStatus.PROCESSING.value}}
    )

    # Trigger inline background processing (no Celery/Redis needed)
    background_tasks.add_task(process_manual_inline, manual_id)

    logger.info(f"Processing started: {manual_id} (job: {job.job_id})")
    
    return ProcessManualResponse(
        job_id=job.job_id,
        manual_id=manual_id,
        status="processing",
        message="Ingestion started. Check /status for progress."
    )


@router.get("/status/{manual_id}", response_model=IngestionStatusResponse)
async def get_ingestion_status(
    manual_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database)
):
    """
    Get the status of a manual ingestion job.
    
    Returns progress, chunks processed, and any errors.
    """
    # Get the manual
    manual_doc = await db.manuals.find_one({"manual_id": manual_id})
    
    if not manual_doc:
        raise HTTPException(status_code=404, detail=f"Manual {manual_id} not found")
    
    manual = dict_to_document(manual_doc, ManualDocument)
    
    # Get the most recent job for this manual
    job_doc = await db.ingestion_jobs.find_one(
        {"manual_id": manual_id},
        sort=[("created_at", -1)]
    )
    
    if not job_doc:
        # No job exists yet, return manual status only
        return IngestionStatusResponse(
            manual_id=manual_id,
            status=manual.status.value,
            progress=0.0,
            chunks_processed=0,
            total_cunks=None,
            error=None,
            started_at=None,
            completed_at=None
        )
    
    job = dict_to_document(job_doc, IngestionJobDocument)
    
    return IngestionStatusResponse(
        manual_id=manual_id,
        status=job.status.value,
        progress=job.progress,
        chunks_processed=job.chunks_processed,
        total_cunks=job.total_chunks,
        error=job.error,
        started_at=job.started_at,
        completed_at=job.completed_at
    )


@router.get("/manuals", response_model=ListManualsResponse)
async def list_manuals(
    db: AsyncIOMotorDatabase = Depends(get_database),
    status: Optional[str] = None
):
    """
    Get all uploaded manuals.
    
    Optional query params:
    - status: Filter by status (pending, processing, completed, failed)
    """
    # Build query
    query = {}
    if status:
        query["status"] = status
    
    # Get all manuals
    cursor = db.manuals.find(query).sort("uploaded_at", -1)
    manual_docs = await cursor.to_list(length=None)
    
    # Convert to response models
    manuals = []
    for doc in manual_docs:
        manual = dict_to_document(doc, ManualDocument)
        manuals.append(ManualListItem(
            manual_id=manual.manual_id,
            pedal_name=manual.pedal_name,
            manufacturer=manual.manufacturer,
            status=manual.status.value,
            chunk_count=manual.chunk_count,
            file_size_bytes=manual.file_size_bytes,
            uploaded_at=manual.uploaded_at,
            indexed_at=manual.indexed_at
        ))
    
    return ListManualsResponse(
        manuals=manuals,
        total=len(manuals)
    )

