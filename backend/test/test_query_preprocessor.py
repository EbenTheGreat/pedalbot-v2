"""
Unit tests for query preprocessing functionality.

Tests typo correction, multi-question detection, and technical term preservation.
"""

import pytest
from backend.services.query_preprocessor import QueryPreprocessor, preprocess_query


class TestQueryPreprocessor:
    """Test cases for QueryPreprocessor."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.preprocessor = QueryPreprocessor()
    
    def test_typo_correction_basic(self):
        """Test basic typo correction."""
        query = "i wnt to bbuy a pedal"
        result = self.preprocessor.preprocess(query)
        
        assert result.normalized_query == "i want to buy a pedal"
        assert len(result.typos_corrected) == 2
        assert any(t["original"] == "wnt" for t in result.typos_corrected)
        assert any(t["original"] == "bbuy" for t in result.typos_corrected)
    
    def test_typo_correction_preserves_technical_terms(self):
        """Test that technical terms are not corrected."""
        query = "Does the Boss DS-1 have USB connectivity?"
        result = self.preprocessor.preprocess(query)
        
        # "DS-1" should be preserved
        assert "DS-1" in result.normalized_query or "DS-1" in query
        assert result.normalized_query == query  # No corrections needed
    
    def test_multi_question_detection(self):
        """Test multi-question detection."""
        query = "i wnt to bbuy 4 and how do i connnect too pc"
        result = self.preprocessor.preprocess(query)
        
        assert result.has_multi_questions is True
        assert len(result.sub_questions) == 2
        # Should split on "and how"
        assert any("buy" in q.lower() for q in result.sub_questions)
        assert any("connect" in q.lower() for q in result.sub_questions)
    
    def test_multi_question_split_patterns(self):
        """Test various multi-question split patterns."""
        test_cases = [
            ("what effects does it have and how much does it cost", 2),
            ("is it good? what about the price", 2),
            ("tell me about distortion, and what's the reverb like", 2),
        ]
        
        for query, expected_count in test_cases:
            result = self.preprocessor.preprocess(query)
            assert result.has_multi_questions is True
            assert len(result.sub_questions) >= expected_count, \
                f"Expected {expected_count} questions in '{query}', got {len(result.sub_questions)}"
    
    def test_single_question_not_split(self):
        """Test that single questions are not incorrectly split."""
        query = "How do I use the delay and reverb together?"
        result = self.preprocessor.preprocess(query)
        
        # "and" here is part of a single question, not a separator
        assert result.has_multi_questions is False or len(result.sub_questions) == 1
    
    def test_typo_correction_with_punctuation(self):
        """Test typo correction preserves punctuation."""
        query = "wnt to bbuy?"
        result = self.preprocessor.preprocess(query)
        
        assert "want" in result.normalized_query
        assert "buy?" in result.normalized_query
    
    def test_spacing_normalization(self):
        """Test extra spacing is normalized."""
        query = "how   do  i    connect"
        result = self.preprocessor.preprocess(query)
        
        assert result.normalized_query == "how do i connect"
    
    def test_confidence_calculation(self):
        """Test confidence score calculation."""
        # Clean query should have high confidence
        clean_query = "What is the input impedance?"
        clean_result = self.preprocessor.preprocess(clean_query)
        assert clean_result.confidence > 0.8
        
        # Typo-heavy query should have lower confidence
        typo_query = "whta is teh efect on teh peadl"
        typo_result = self.preprocessor.preprocess(typo_query)
        assert typo_result.confidence < 0.85  # Penalized for many typos
    
    def test_original_query_preserved(self):
        """Test that original query is preserved."""
        query = "wnt to bbuy"
        result = self.preprocessor.preprocess(query)
        
        assert result.original_query == query
        assert result.normalized_query != query
    
    def test_complex_multiquestion_with_typos(self):
        """Test the exact query from user's issue."""
        query = "i wnt to bbuy 4 and how do i connnect too pc"
        result = self.preprocessor.preprocess(query)
        
        # Should correct typos
        assert "want" in result.normalized_query
        assert "buy" in result.normalized_query
        assert "connect" in result.normalized_query
        assert "to" in result.normalized_query
        
        # Should detect multi-question
        assert result.has_multi_questions is True
        assert len(result.sub_questions) == 2
        
        # Should track corrections
        assert len(result.typos_corrected) >= 4  # wnt, bbuy, connnect, too
    
    def test_technical_term_patterns(self):
        """Test various technical term patterns are preserved."""
        queries = [
            "Does the MXR M234 have MIDI?",
            "What's the impedance in kHz?",
            "Is it 1/4 inch or XLR?",
            "Boss CE-5 vs Boss BD-2",
        ]
        
        for query in queries:
            result = self.preprocessor.preprocess(query)
            # Technical terms should be preserved
            assert any(
                term in result.normalized_query 
                for term in ["MXR", "M234", "MIDI", "kHz", "1/4", "XLR", "CE-5", "BD-2"]
                if term in query
            )
    
    def test_empty_query(self):
        """Test handling of empty query."""
        result = self.preprocessor.preprocess("")
        assert result.normalized_query == ""
        assert len(result.typos_corrected) == 0
        assert result.has_multi_questions is False
    
    def test_convenience_function(self):
        """Test the convenience function works."""
        result = preprocess_query("wnt to bbuy")
        assert result.normalized_query == "want to buy"


class TestQueryPreprocessorEdgeCases:
    """Edge case tests for QueryPreprocessor."""
    
    def test_all_caps_query(self):
        """Test query with all caps."""
        preprocessor = QueryPreprocessor()
        query = "WNT TO BBUY A PEDAL"
        result = preprocessor.preprocess(query)
        
        # Should still correct typos
        assert "WANT" in result.normalized_query or "want" in result.normalized_query
    
    def test_very_long_query(self):
        """Test handling of very long queries."""
        preprocessor = QueryPreprocessor()
        query = "i wnt to know " + " ".join(["what"] * 50) + " and how do i connnect"
        result = preprocessor.preprocess(query)
        
        assert result.normalized_query is not None
        assert "want" in result.normalized_query
    
    def test_special_characters(self):
        """Test queries with special characters."""
        preprocessor = QueryPreprocessor()
        query = "wnt to bbuy @ $100!!!"
        result = preprocessor.preprocess(query)
        
        assert "want" in result.normalized_query
        assert "$100" in result.normalized_query


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
