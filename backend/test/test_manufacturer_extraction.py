"""
Test manufacturer extraction from both filename and PDF.

This validates the cascading extraction strategy:
1. Try filename first
2. Try PDF if filename fails
3. Fallback to None
"""
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from backend.routers.ingest import _extract_manufacturer_from_filename
from backend.workers.ingest_worker import _extract_manufacturer_from_pdf

print("=" * 60)
print("MANUFACTURER EXTRACTION TEST")
print("=" * 60)

# Test 1: Filename extraction
print("\n📁 FILENAME EXTRACTION\n")

filename_tests = [
    ("boss_gt1_eng03_manual.pdf", "Boss"),
    ("line6_helix_manual.pdf", "Line 6"),
    ("zoom_g3xn_user_guide.pdf", "Zoom"),
    ("tc_electronic_hall_of_fame.pdf", "TC Electronic"),
    ("mxr_phase_90.pdf", "MXR"),
    ("strymon_timeline.pdf", "Strymon"),
    ("GT-1_eng03_W.pdf", None),  # No manufacturer in filename
    ("manual.pdf", None),  # Generic filename
]

for filename, expected in filename_tests:
    result = _extract_manufacturer_from_filename(filename)
    status = "✅" if result == expected else "❌"
    print(f"{status} '{filename}' → {result or 'None'}")
    if result != expected:
        print(f"   Expected: {expected}")

# Test 2: PDF content extraction
print("\n📄 PDF CONTENT EXTRACTION\n")

# Simulate PDF chunks
class MockChunk:
    def __init__(self, content):
        self.page_content = content

pdf_tests = [
    (
        [MockChunk("BOSS GT-1: Guitar Effects Processor\n© 2016 Roland Corporation")],
        "Boss"
    ),
    (
        [MockChunk("Line 6 Helix Owner's Manual\nVersion 3.80")],
        "Line 6"
    ),
    (
        [MockChunk("Zoom G3Xn Multi-Effects Processor\nUser Guide")],
        "Zoom"
    ),
    (
        [MockChunk("Kemper Profiler Amplifier\n© 2023 Kemper GmbH")],
        "Kemper"
    ),
    (
        [MockChunk("Generic pedal manual with no manufacturer info")],
        None
    ),
]

for chunks, expected in pdf_tests:
    result = _extract_manufacturer_from_pdf(chunks, {})
    status = "✅" if result == expected else "❌"
    content_preview = chunks[0].page_content[:50].replace("\n", " ")
    print(f"{status} '{content_preview}...' → {result or 'None'}")
    if result != expected:
        print(f"   Expected: {expected}")

# Test 3: Cascading strategy simulation
print("\n🔄 CASCADING STRATEGY\n")

cascade_tests = [
    ("boss_gt1_manual.pdf", [MockChunk("Some content")], "Boss", "filename"),
    ("manual.pdf", [MockChunk("BOSS GT-1: Guitar Effects")], "Boss", "pdf"),
    ("generic.pdf", [MockChunk("No manufacturer info")], None, "none"),
]

for filename, chunks, expected, source in cascade_tests:
    # First attempt: filename
    from_filename = _extract_manufacturer_from_filename(filename)
    
    # Second attempt: PDF (only if filename failed)
    from_pdf = None
    if not from_filename:
        from_pdf = _extract_manufacturer_from_pdf(chunks, {})
    
    final_result = from_filename or from_pdf
    status = "✅" if final_result == expected else "❌"
    
    actual_source = "filename" if from_filename else ("pdf" if from_pdf else "none")
    print(f"{status} '{filename}' → {final_result or 'None'} (from {actual_source})")
    if final_result != expected or actual_source != source:
        print(f"   Expected: {expected} from {source}")

print("\n" + "=" * 60)
print("✨ CASCADING MANUFACTURER EXTRACTION TEST COMPLETE!")
print("=" * 60)
