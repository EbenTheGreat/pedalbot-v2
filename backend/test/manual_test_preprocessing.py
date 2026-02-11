"""
Manual test script for query preprocessing.
Tests the exact user query from the issue.
"""

import sys
sys.path.append('/Users/solomonolakulehin/Desktop/eben/pedalbot-langgraph-main')

from backend.services.query_preprocessor import QueryPreprocessor

def test_user_query():
    """Test the exact query from the user's issue."""
    preprocessor = QueryPreprocessor()
    
    # The problematic query
    query = "i wnt to bbuy 4 and how do i connnect too pc"
    
    print("=" * 80)
    print("QUERY PREPROCESSING TEST")
    print("=" * 80)
    print(f"\n📝 Original Query: \"{query}\"")
    print()
    
    result = preprocessor.preprocess(query)
    
    print(f"✅ Normalized Query: \"{result.normalized_query}\"")
    print()
    
    print(f"🔧 Typos Corrected ({len(result.typos_corrected)}):")
    for typo in result.typos_corrected:
        print(f"   - '{typo['original']}' → '{typo['corrected']}'")
    print()
    
    print(f"❓ Multi-Question: {result.has_multi_questions}")
    if result.has_multi_questions:
        print(f"   Sub-Questions ({len(result.sub_questions)}):")
        for i, sub_q in enumerate(result.sub_questions, 1):
            print(f"   {i}. \"{sub_q}\"")
    print()
    
    print(f"🎯 Confidence Score: {result.confidence:.2f}")
    print()
    
    # Test expectations
    print("=" * 80)
    print("VALIDATION")
    print("=" * 80)
    
    passed = []
    failed = []
    
    # Check 1: Typo corrections
    if "want" in result.normalized_query and "buy" in result.normalized_query:
        passed.append("✓ Typos corrected (wnt→want, bbuy→buy)")
    else:
        failed.append("✗ Typos not corrected properly")
    
    # Check 2: Multi-question detection
    if result.has_multi_questions and len(result.sub_questions) == 2:
        passed.append("✓ Multi-question detected (2 sub-questions)")
    else:
        failed.append(f"✗ Multi-question detection failed (got {len(result.sub_questions)} questions)")
    
    # Check 3: Technical preservation
    if "connect" in result.normalized_query and "pc" in result.normalized_query.lower():
        passed.append("✓ Technical terms preserved")
    else:
        failed.append("✗ Technical terms not preserved")
    
    print("\nPASSED:")
    for p in passed:
        print(f"  {p}")
    
    if failed:
        print("\nFAILED:")
        for f in failed:
            print(f"  {f}")
    else:
        print("\n🎉 ALL CHECKS PASSED!")
    
    print("\n" + "=" * 80)
    
    return len(failed) == 0

if __name__ == "__main__":
    success = test_user_query()
    sys.exit(0 if success else 1)
