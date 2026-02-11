#!/usr/bin/env python3
"""
Quick test to see if query preprocessing works for the NUX MG-30 query.
"""

import asyncio
from backend.services.query_preprocessor import QueryPreprocessor

def main():
    """Test preprocessing."""
    preprocessor = QueryPreprocessor()
    
    test_query = "how do i put it on and i wnt to buy 3"
    
    print(f"Original Query: {test_query}")
    print("-" * 60)
    
    result = preprocessor.preprocess(test_query)
    
    print(f"Normalized Query: {result.normalized_query}")
    print(f"Has Multi-Questions: {result.has_multi_questions}")
    print(f"Sub-Questions: {result.sub_questions}")
    print(f"Typos Corrected: {result.typos_corrected}")
    print(f"Confidence: {result.confidence:.2f}")
    print("-" * 60)
    
    # Check if "wnt" was corrected to "want"
    if "want" in result.normalized_query and "wnt" not in result.normalized_query:
        print("✅ Typo correction WORKING: 'wnt' → 'want'")
    else:
        print("❌ Typo correction FAILED: 'wnt' not corrected")
    
    # Check if multi-question was detected
    if result.has_multi_questions:
        print(f"✅ Multi-question detection WORKING: {len(result.sub_questions)} parts")
    else:
        print("❌ Multi-question detection FAILED")

if __name__ == "__main__":
    main()
