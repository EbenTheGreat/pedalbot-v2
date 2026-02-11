"""
Test script for extreme typo handling.
Tests the problematic query that caused an error.
"""

import sys
sys.path.append('/Users/solomonolakulehin/Desktop/eben/pedalbot-langgraph-main')

from backend.services.query_preprocessor import QueryPreprocessor

def test_extreme_typos():
    """Test extreme typo cases."""
    preprocessor = QueryPreprocessor()
    
    test_cases = [
        # Original working queries
        ("hriw do i buy 4 of these", "Severe typo 'hriw'"),
        ("how bout connecting to a pc", "Casual 'bout'"),
        
        # The problematic query that failed
        ("if i want to bbuy 3 and r=th=urn the pedal on", "Failed query with r=th=urn"),
        
        # More extreme cases
        ("i wnt too connnect my peadl", "Multiple typos"),
        ("whta efects does teh pedla have", "Multiple typos"),
        ("cann i byy thiss guitarr peadl", "Doubled letters"),
    ]
    
    print("="*80)
    print("EXTREME TYPO CORRECTION TESTS")
    print("="*80)
    
    for query, description in test_cases:
        print(f"\n📝 Test: {description}")
        print(f"   Input:  \"{query}\"")
        
        try:
            result = preprocessor.preprocess(query)
            print(f"   Output: \"{result.normalized_query}\"")
            
            if result.typos_corrected:
                print(f"   Typos:  {len(result.typos_corrected)} corrections")
                for typo in result.typos_corrected[:3]:
                    print(f"           - {typo['original']} → {typo['corrected']}")
            
            if result.has_multi_questions:
                print(f"   Multi:  {len(result.sub_questions)} questions detected")
            
            print(f"   ✅ SUCCESS")
            
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n" + "="*80)

if __name__ == "__main__":
    test_extreme_typos()
