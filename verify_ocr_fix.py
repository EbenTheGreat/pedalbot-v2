import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.services.pdf_processor import PdfProcessor
from backend.config.config import settings

# Configure logging to see our diagnostic info
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ocr_processing():
    print("\n🔍 Verifying OCR Fix & Memory Optimization\n")
    print("=" * 60)
    
    import json
    with open("google-vision-credentials.json", "r") as f:
        creds = json.load(f)

    # Initialize processor
    processor = PdfProcessor(
        chunk_size=300,
        chunk_overlap=100,
        google_credentials_json=creds,
        ocr_quality_threshold=0.3
    )
    
    # Path to a test PDF
    pdf_path = "uploads_dir/_home_httpd_data_media-data_2_NUX_MG30_UserManual_English-.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"❌ Test PDF not found at {pdf_path}")
        return

    print(f"Processing {pdf_path} (Hybrid OCR enabled)...")
    
    try:
        # Process ONLY the first 2 pages to save time/cost but still verify logic
        import pymupdf
        doc = pymupdf.open(pdf_path)
        # We'll mock the process_pdf slightly to only do first 2 pages if we wanted, 
        # but let's just run the full thing on this smaller PDF (2.1MB)
        
        chunks, metadata = processor.process_pdf(
            pdf_path=pdf_path,
            pedal_name="NUX MG-30",
            force_ocr=True  # Force OCR to test our improvements
        )
        
        print(f"\n✅ Processing complete!")
        print(f"Total chunks: {len(chunks)}")
        print(f"Quality score (after OCR): {metadata.get('quality_score_after_ocr', 'N/A')}")
        
        # Check for smushed word fixes
        print("\n📝 Sample Text Output (checking for word boundaries):")
        print("-" * 30)
        
        # Find chunks likely to have smushed text artifacts
        # (Looking for common technical terms)
        keywords = ["input", "output", "jack", "power", "mono", "stereo"]
        found_sample = False
        
        for chunk in chunks[:10]:
            text = chunk.text.lower()
            if any(k in text for k in keywords):
                print(f"Page {chunk.page_number}: {chunk.text[:500]}...")
                print("-" * 30)
                found_sample = True
                break
        
        if not found_sample and chunks:
            print(f"Page {chunks[0].page_number}: {chunks[0].text[:500]}...")
            print("-" * 30)

    except Exception as e:
        print(f"❌ Error during processing: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_ocr_processing())
