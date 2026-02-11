"""
PDF processing and chunking for pedal manuals.

Handles:
- Text extraction from PDFs (with OCR fallback via Google Vision API)
- Intelligent chunking with overlap
- Metadata extraction (page numbers, sections)
- Quality scoring
"""
from typing import List, Dict, Tuple, Any, Optional
import re
import logging
from dataclasses import dataclass
from pathlib import Path
from google.cloud import vision
from google.oauth2 import service_account
import pymupdf  
import io
import base64

logger = logging.getLogger(__name__)

@dataclass
class PdfChunk:
    """A single chunk of text from a PDF with metadata."""
    text: str
    chunk_index: int
    page_number: int
    section: Optional[str] = None  # e.g., "specifications", "controls"
    char_count: int = 0
    token_estimate: int = 0  # Rough estimate (chars / 4)


    def __post_init__(self):
        self.char_count = len(self.text)
        self.token_estimate = self.char_count // 4

    def to_metadata(self) -> Dict[str, Any]:
        """Convert to metadata dict for Pinecone."""
        return {
            "text": self.text,
            "chunk_index": self.chunk_index,
            "page_number": self.page_number,
            "section": self.section or "general",
            "char_count": self.char_count,
            "token_estimate": self.token_estimate
        }
    

class PdfProcessor:
    """
    Process pedal manual PDFs into chunks for vector storage.
    
    Supports automatic OCR via Google Vision API for image-based PDFs.
    
    Usage:
        processor = PDFProcessor(
            chunk_size=500,
            chunk_overlap=50,
            google_credentials_path="path/to/credentials.json"  # Optional
        )
        
        chunks, metadata = processor.process_pdf(
            pdf_path="boss_ds1_manual.pdf",
            pedal_name="Boss DS-1",
            force_ocr=False  # Auto-detect or force OCR
        )
    """

    def __init__(self,
                chunk_size: int=300,
                chunk_overlap: int=100,
                min_chunk_size: int=10,
                max_chunk_size: int=5000,
                google_api_key: Optional[str] = None,
                google_credentias_path: Optional[str]=None,
                google_credentials_json: Optional[Dict[str, Any]]=None,
                ocr_quality_threshold: float=0.3):
        """
        Initialize PDF processor.
        
        Args:
            chunk_size: Target size in tokens (chars / 4)
            chunk_overlap: Overlap between chunks in tokens
            min_chunk_size: Minimum chunk size (skip smaller)
            max_chunk_size: Maximum chunk size (hard limit)
            google_api_key: Google Cloud API key (simplest option)
            google_credentials_path: Path to Google Cloud credentials JSON
            google_credentials_json: Google Cloud credentials as dict
            ocr_quality_threshold: If quality score < this, use OCR
        """

        self.chunk_size = chunk_size
        self.chunk_overlap= chunk_overlap
        self.min_chunk_size= min_chunk_size
        self.max_chunk_size= max_chunk_size
        self.ocr_quality_threshold = ocr_quality_threshold

        # Convert to characters (rough estimate: 1 token ≈ 4 chars)
        self.chunk_size_chars = chunk_size * 4
        self.chunk_overlap_chars = chunk_overlap * 4
        self.min_chunk_chars= min_chunk_size * 4
        self.max_chunk_chars = max_chunk_size * 4

        # Initialize Google Vision client if credentials provided
        self.vision_client = None

        if google_credentials_json:
            # Use service account credentials (dict) - PREFERRED method
            try:
                credentials = service_account.Credentials.from_service_account_info(
                    google_credentials_json
                )
                self.vision_client = vision.ImageAnnotatorClient(credentials=credentials)
                logger.info(f"Google Vision API initialized with service account for project: {google_credentials_json.get('project_id')}")
            
            except Exception as e:
                logger.warning(f"Failed to initialize Google Vision with service account: {e}. OCR disabled")

        elif google_credentias_path:
            # Use service account JSON file
            try:
                credentials = service_account.Credentials.from_service_account_file(
                    google_credentias_path
                )
                self.vision_client = vision.ImageAnnotatorClient(credentials=credentials)
                logger.info("Google Vision API initialized with service account file")

            except Exception as e:
                logger.warning(f"Failed to initialize Google Vision: {e}. OCR will be disabled.")
                self.vision_client = None

        elif google_api_key:
            # Use API key (fallback)
            try:
                import google.api_core.client_options as client_options

                client_opts = client_options.ClientOptions(api_key=google_api_key)
                self.vision_client = vision.ImageAnnotatorClient(client_options=client_opts)
                logger.info("Google Vision API initialized with API Key")
            
            except Exception as e:
                logger.warning(f"Failed to initialize Google Vision API with Api key: {e}. OCR disabled")

    def process_pdf(self,
                    pdf_path: str,
                    pedal_name: str,
                    force_ocr: bool = False) -> Tuple[list[PdfChunk] , Dict[str, Any]]:
        """
        Process a PDF into chunks.
        
        Args:
            pdf_path: Path to PDF file (local or URL)
            pedal_name: Name of the pedal (for context)
            force_ocr: Force OCR even if text extraction works
        
        Returns:
            Tuple of (chunks, pdf_metadata)
        """

        logger.info(f"Procesing PDF: {pdf_path}")

        try:
            # Open PDF
            doc = pymupdf.open(pdf_path)

            # Extract metadata
            pdf_metadata = self._extract_pdf_metadata(doc, pedal_name)

            # Try standard text extraction first
            full_text, page_map = self._extract_text_from_pdf(doc)

            # Calculate quality score
            quality_score = self._calculate_quality_score(full_text, pdf_metadata)

            pdf_metadata["quality_score"] = quality_score

            # Decide if OCR is needed
            needs_ocr = force_ocr or quality_score < self.ocr_quality_threshold

            if needs_ocr:
                if self.vision_client:
                    logger.info(f"Using Hybrid Extraction (Text Layer + OCR)... Quality score: {quality_score:.2f}")
                    pdf_metadata["ocr_used"] = True

                    # Perform Hybrid OCR on all pages
                    full_text, page_map = self._extract_text_hybrid(doc)

                    # Recalculate quality score
                    quality_score = self._calculate_quality_score(full_text, pdf_metadata)
                    pdf_metadata["quality_score_after_ocr"] = quality_score
                    logger.info(f"Hybrid extraction complete. New quality score: {quality_score:.2f}")


                else:
                    logger.warning(
                        f"OCR needed (quality: {quality_score:.2f}) but Google Vision not initialized. "
                        "Proceeding with extracted text."
                    )
                    pdf_metadata["ocr_required"] = True
                    pdf_metadata["ocr_used"] = False
            else:
                pdf_metadata["ocr_used"] = False

            # Close document
            doc.close()    

            # Detect sections (table of contents, specifications, etc.)
            sections = self._detect_sections(full_text)  

            # Chunk the text
            chunks = self._chunk_text(full_text, page_map, sections) 

            logger.info(f"Processed PDF: {len(chunks)} chunks, {pdf_metadata['page_count']} pages")

            return chunks, pdf_metadata
        
        except Exception as e:
            logger.error(f"Failed to process PDF {pdf_path}: {e}")
            raise

    def _extract_pdf_metadata(self, doc: pymupdf.Document, pedal_name: str) -> Dict[str, Any]:
        """Extract PDF metadata."""
        metadata = doc.metadata or {}

        return {
            "pedal_name": pedal_name,
            "page_count": len(doc),
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "creator": metadata.get("creator", ""),
            "file_size_byte": 0
        }
    
    def _extract_text_from_pdf(self, doc: pymupdf.Document) -> Tuple[str, Dict[int, int]]:
        """
        Extract text from all pages using PyMuPDF.
        
        Returns:
            Tuple of (full_text, page_map) where page_map maps char position → page number
        """

        full_text = ""
        page_map= {}  # Maps character position to page number

        for page_num, page in enumerate(doc.pages(), start=1):
            # Extract text
            page_text = page.get_text("text")

            # Clean up
            page_text = self._clean_text(page_text)

            # Track page boundaries
            start_pos = len(full_text)
            full_text += page_text + "\n\n"
            end_pos = len(full_text)

            # Map every character position to this page
            for pos in range(start_pos, end_pos):
                page_map[pos] = page_num
        
        return full_text.strip(), page_map


    def _extract_text_hybrid(self, doc: pymupdf.Document) -> Tuple[str, Dict[int, int]]:
        """
        Extract text using a hybrid approach:
        1. Extract text layer via PyMuPDF (blocks with bounding boxes)
        2. Extract OCR text via Google Vision (blocks with bounding boxes)
        3. Merge them, preferring text layer for overlapping areas,
           and keeping OCR for diagram labels/text not in layer.
        
        Returns:
            Tuple of (full_text, page_map)
        """
        logger.info(f"_extract_text_hybrid called. vision_client exists: {self.vision_client is not None}")
        
        if not self.vision_client:
            logger.warning("Vision client is None in _extract_text_hybrid - falling back to text extraction only")
            return self._extract_text_from_pdf(doc)

        full_text = ""
        page_map = {}
        total_pages = len(doc)
        logger.info(f"Starting hybrid extraction for {total_pages} pages")

        for page_num, page in enumerate(doc.pages(), start=1):
            logger.info(f"Hybrid extraction on page {page_num}/{total_pages}")
            
            # 1. Get Text Layer via Words to reconstruct spaces properly (fixes 'smushed' text)
            words = page.get_text("words")
            layer_blocks = []
            if words:
                # Group words into blocks using the block number provided by PyMuPDF
                reconstructed_blocks = {}
                for w in words:
                    # w = (x0, y0, x1, y1, "word", block_no, line_no, word_no)
                    b_idx = w[5]
                    if b_idx not in reconstructed_blocks:
                        reconstructed_blocks[b_idx] = {
                            'x0': w[0], 'y0': w[1], 'x1': w[2], 'y1': w[3],
                            'words': []
                        }
                    reconstructed_blocks[b_idx]['words'].append(w[4])
                    reconstructed_blocks[b_idx]['x0'] = min(reconstructed_blocks[b_idx]['x0'], w[0])
                    reconstructed_blocks[b_idx]['y0'] = min(reconstructed_blocks[b_idx]['y0'], w[1])
                    reconstructed_blocks[b_idx]['x1'] = max(reconstructed_blocks[b_idx]['x1'], w[2])
                    reconstructed_blocks[b_idx]['y1'] = max(reconstructed_blocks[b_idx]['y1'], w[3])
                
                for b_idx, data in reconstructed_blocks.items():
                    # Format: (x0, y0, x1, y1, "text", block_no, block_type)
                    layer_blocks.append((
                        data['x0'], data['y0'], data['x1'], data['y1'],
                        " ".join(data['words']), b_idx, 0 # 0 = text
                    ))
            else:
                # Fallback to standard blocks if words extraction returns nothing
                layer_blocks = page.get_text("blocks")
            
            # 2. Get OCR Results
            logger.info(f"Page {page_num}: Rendering pixmap for OCR...")
            pix = page.get_pixmap(dpi=300)
            img_bytes = pix.tobytes("png")
            logger.info(f"Page {page_num}: Rendered {len(img_bytes)} bytes PNG image")
            
            image = vision.Image(content=img_bytes)
            feature = vision.Feature(type=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            request = vision.AnnotateImageRequest(image=image, features=[feature])
            
            ocr_blocks_to_add = []
            
            try:
                logger.info(f"Page {page_num}: Calling Google Vision API...")
                response = self.vision_client.annotate_image(request=request)
                logger.info(f"Page {page_num}: Vision API responded successfully")
                if response.full_text_annotation:
                    # Process OCR blocks
                    for vision_block in response.full_text_annotation.pages[0].blocks:
                        bbox = vision_block.bounding_box
                        vx = [v.x for v in bbox.vertices if v.x is not None]
                        vy = [v.y for v in bbox.vertices if v.y is not None]
                        
                        if not vx or not vy: continue
                        
                        ox0, oy0, ox1, oy1 = min(vx), min(vy), max(vx), max(vy)
                        
                        # Get text for this block
                        text_parts = []
                        for para in vision_block.paragraphs:
                            para_text = "".join(["".join([symbol.text for symbol in word.symbols]) + (" " if word.property.detected_break.type in [1, 2, 3] else "") for word in para.words])
                            text_parts.append(para_text.strip())
                        
                        b_text = " ".join(text_parts).strip()
                        if not b_text: continue
                        
                        # Check overlap with ANY layer block
                        is_duplicate = False
                        for lx0, ly0, lx1, ly1, ltext, lno, ltype in layer_blocks:
                            if ltype != 0: continue
                            
                            scale = 300 / 72
                            sx0, sy0, sx1, sy1 = lx0*scale, ly0*scale, lx1*scale, ly1*scale
                            
                            ix0 = max(ox0, sx0)
                            iy0 = max(oy0, sx0)
                            ix1 = min(ox1, sx1)
                            iy1 = min(oy1, sy1)
                            
                            if ix1 > ix0 and iy1 > iy0:
                                inter_area = (ix1 - ix0) * (iy1 - iy0)
                                ocr_area = (ox1 - ox0) * (oy1 - oy0)
                                if (inter_area / ocr_area) > 0.4:
                                    is_duplicate = True
                                    break
                        
                        if not is_duplicate:
                            ocr_blocks_to_add.append({
                                'x0': ox0, 'y0': oy0, 'x1': ox1, 'y1': oy1,
                                'text': b_text, 'source': 'ocr'
                            })
                            
            except Exception as e:
                logger.error(f"OCR failed for page {page_num}: {e}")

            # 3. Merge and Sort
            all_blocks = []
            for lx0, ly0, lx1, ly1, ltext, lno, ltype in layer_blocks:
                if ltype == 0:
                    scale = 300 / 72
                    all_blocks.append({
                        'x0': lx0*scale, 'y0': ly0*scale, 'x1': lx1*scale, 'y1': ly1*scale,
                        'text': self._clean_text(ltext), 'source': 'layer'
                    })
            
            all_blocks.extend(ocr_blocks_to_add)
            all_blocks.sort(key=lambda b: (b['y0'] // 10, b['x0']))
            
            page_text = "\n".join([b['text'] for b in all_blocks if b['text']])
            
            start_pos = len(full_text)
            full_text += page_text + "\n\n"
            end_pos = len(full_text)
            
            for pos in range(start_pos, end_pos):
                page_map[pos] = page_num
                
        return full_text.strip(), page_map

    def _extract_text_with_ocr(self, doc: pymupdf.Document) -> Tuple[str, Dict[int, int]]:
        """Extract text from all pages using Google Vision OCR only."""

        if not self.vision_client:
            raise RuntimeError("Google Vision client not initialized for OCR.")

        full_text = ""
        page_map= {}  # Maps character position to page number

        for page_num, page in enumerate(doc.pages(), start=1):
            logger.info(f"Running OCR on page {page_num}/{len(doc)}")

            # Render page to image
            pix = page.get_pixmap(dpi=300)  # High DPI for better OCR
            img_bytes = pix.tobytes("png")

            # Prepare image for Google Vision
            image = vision.Image(content=img_bytes)
            feature = vision.Feature(type=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
            request = vision.AnnotateImageRequest(image=image, features=[feature])
            

            # Perform OCR
            try:
                response = self.vision_client.annotate_image(request=request)
                
                if response.error.message:
                    logger.error(f"OCR error on page {page_num}: {response.error.message}")
                    page_text = ""
                else:
                    # Get full text annotation
                    page_text = response.full_text_annotation.text if response.full_text_annotation else ""
                    
                    # Clean text
                    page_text = self._clean_text(page_text)
                
            except Exception as e:
                logger.error(f"OCR failed on page {page_num}: {e}")
                page_text = ""
            
            # Track page boundaries
            start_pos = len(full_text)
            full_text += page_text + "\n\n"
            end_pos = len(full_text)
            
            # Map every character position to this page
            for pos in range(start_pos, end_pos):
                page_map[pos] = page_num
        
        return full_text.strip(), page_map
    

    def _clean_text(self, text: str) -> str:
        """Clean extracted text."""
        if not text:
            return ""

        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Add spaces after bullets if they are stuck to text (common extraction error)
        # Handles both *Word and *1Word patterns
        text = re.sub(r'([*•●])(?=[a-zA-Z0-9])', r'\1 ', text)
        
        # Light heuristic for smushed CamelCase headings (e.g., TurningOn -> Turning On)
        # Avoids splitting common technical terms by requiring 3+ lowercase then a Capital
        text = re.sub(r'([a-z]{3,})([A-Z])', r'\1 \2', text)

        # Remove page numbers (common patterns at end of lines)
        text = re.sub(r'\b\d{1,3}\b\s*$', '', text)

        # Fix common OCR/PDF ligatures
        ligatures = {
            'ﬁ': 'fi', 'ﬂ': 'fl', 'ﬀ': 'ff', 'ﬃ': 'ffi', 'ﬄ': 'ffl',
        }
        for lig, rep in ligatures.items():
            text = text.replace(lig, rep)

        return text.strip()

    def _calculate_quality_score(self, text: str, metadata: Dict[str, Any]) -> float:
        """
        Calculate quality score (0-1) based on text extraction.
        
        Low score indicates OCR may be needed.
        """

        if not text:
            return 0.0
        
        # Average characters per page
        avg_chars_per_page = len(text) / max(metadata["page_count"], 1)

        # Heuristics
        score = 1.0

        # Too few chars per page (likely scanned without OCR)
        if avg_chars_per_page < 100:
            score *= 0.3

        # Check for common words (indicates readable text)
        common_words = ["the", "and", "to", "of", "a", "in", "is"]
        word_count = sum(1 for word in common_words if word in text.lower())
        if word_count < 3:
            score *= 0.5

        # Check for garbled text (OCR artifacts)
        garbled_ratio = len(re.findall(r'[^\w\s\.,;:\-\(\)]+', text)) / max(len(text), 1)
        if garbled_ratio > 0.1:
            score *= 0.6
        
        return max(0.0, min(1.0, score))
        
    def _detect_sections(self, text: str) -> Dict[str, Tuple[int, int]]:
        """
        Detect common sections in pedal manuals.
        
        Returns:
            Dict mapping section name → (start_pos, end_pos)
        """
        sections = {}

        # Common section headers in pedal manuals
        section_patterns = {
            "specifications": r"(?i)\b(?:specifications?|specs?|technical\s+data)\b",
            "controls": r"(?i)\b(?:controls?|knobs?|switches?|panel)\b",
            "connections": r"(?i)\b(?:connections?|jacks?|inputs?|outputs?)\b",
            "features": r"(?i)\b(?:features?|overview|introduction)\b",
            "operation": r"(?i)\b(?:operation|how\s+to\s+use|usage)\b",
            "settings": r"(?i)\b(?:settings?|recommended|sound\s+samples?)\b",
        }

        for section_name, pattern in section_patterns.items():
            matches = list(re.finditer(pattern, text))
            if matches:
                # Take first match as section start
                start_pos = matches[0].start()
                sections[section_name] = (start_pos, start_pos + 1000) # Rough end
        return sections
    
    
    def _chunk_text(self, text: str, page_map: Dict[int, int],
                    sections: Dict[str, Tuple[int, int]]) -> List[PdfChunk]:
        """
        Chunk text with overlap and metadata.
        
        Uses sliding window approach with sentence boundary awareness.
        """

        chunks = []
        chunk_index = 0
        start = 0

        # Split into sentences for better chunking
        sentences = self._split_into_sentences(text)
        sentence_positions = []

        # Calculate sentence positions
        current_pos = 0
        for sentence in sentences:
            sentence_positions.append((current_pos, current_pos + len(sentence)))
            current_pos += len(sentence)
        
        # Chunk by sentences
        current_chunk_sentences = []
        current_chunk_size = 0

        for i, sentence in enumerate(sentences):
            sentence_len = len(sentence)

            # Add sentence to current chunk
            current_chunk_sentences.append(sentence)
            current_chunk_size += sentence_len

            # Check if chunk is large enough
            if current_chunk_size >= self.chunk_size_chars:
                # Create chunk
                chunk_text = " ".join(current_chunk_sentences)

                # Get page number from middle of chunk
                chunk_start = sentence_positions[i - len(current_chunk_sentences) + 1][0]
                chunk_mid = chunk_start + len(chunk_text) // 2
                page_number = page_map.get(chunk_mid, 1)

                # Detect section
                section = self._find_section_for_position(chunk_start, sections)
                
                # Create chunk object
                if len(chunk_text) >= self.min_chunk_chars:
                    chunk = PdfChunk(
                        text=chunk_text.strip(),
                        chunk_index=chunk_index,
                        page_number=page_number,
                        section=section,
                    )
                    chunks.append(chunk)
                    chunk_index += 1

                # Calculate overlap: keep last N sentences
                overlap_size = 0
                overlap_sentences = []

                for sentence in reversed(current_chunk_sentences):
                    if overlap_size + len(sentence) <= self.chunk_overlap_chars:
                        overlap_sentences.insert(0, sentence)
                        overlap_size += len(sentence)
                    else:
                        break
                
                # Start next chunk with overlap
                current_chunk_sentences = overlap_sentences
                current_chunk_size = overlap_size

        # Add final chunk if any
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            if len(chunk_text) >= self.min_chunk_chars:
                chunk_start = sentence_positions[-len(current_chunk_sentences)][0]
                chunk_mid = chunk_start + len(chunk_text) // 2
                page_number = page_map.get(chunk_mid, 1)
                section = self._find_section_for_position(chunk_start, sections)
                
                chunk = PdfChunk(
                    text=chunk_text.strip(),
                    chunk_index=chunk_index,
                    page_number=page_number,
                    section=section,
                )
                chunks.append(chunk)
        
        return chunks    

    def _split_into_sentences(self, text: str) -> List[str]:
        """
        Split text into processing units (sentences or lines).
        
        Handles:
        - Standard punctuation (. ! ?)
        - Newlines (common in lists and specs)
        """
        if not text:
            return []
            
        # Split by newlines first
        lines = text.split('\n')
        
        all_units = []
        sentence_endings = re.compile(r'(?<=[.!?]) +')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Split line further by punctuation if it contains multiple sentences
            sub_units = sentence_endings.split(line)
            for unit in sub_units:
                unit = unit.strip()
                if unit:
                    all_units.append(unit)
                    
        return all_units
    
    def _find_section_for_position(self, position: int,
                                sections: Dict[str, Tuple[int, int]]) -> Optional[str]:
        """Find which section a position belongs to."""
        for section_name, (start, end) in sections.items():
            if start <= position <= end:
                return section_name
        return None 

    def get_chunk_texts(self, chunks: List[PdfChunk]) -> List[str]:
        """Extract just the text from chunks (for embedding)."""
        return [chunk.text for chunk in chunks]
    
    def get_chunk_metadata(self, chunks: List[PdfChunk]) -> List[Dict[str, Any]]:
        """Extract metadata from chunks (for Pinecone)."""
        return [chunk.to_metadata() for chunk in chunks]
    


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def estimate_tokens(text: str) -> int:
    """Rough token estimate (GPT-style: ~4 chars per token)."""
    return len(text) // 4


def validate_pdf(pdf_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate PDF file.
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        doc = pymupdf.open(pdf_path)
        
        # Check if PDF is empty
        if len(doc) == 0:
            return False, "PDF has no pages"
        
        # Check if PDF is encrypted
        if doc.is_encrypted:
            return False, "PDF is encrypted"
        
        # Try to extract text from first page
        first_page_text = doc[0].get_text("text")
        
        doc.close()
        
        return True, None
        
    except Exception as e:
        return False, str(e)


def get_pdf_file_size(pdf_path: str) -> int:
    """Get PDF file size in bytes."""
    return Path(pdf_path).stat().st_size  
