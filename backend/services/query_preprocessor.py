"""
Query Preprocessor: Normalizes user queries for better agent performance.

Features:
1. Typo correction for common misspellings
2. Multi-question detection and splitting
3. Query normalization (spacing, capitalization)
4. Technical term preservation
"""

import re
import logging
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PreprocessingResult:
    """Result of query preprocessing."""
    normalized_query: str
    original_query: str
    typos_corrected: List[Dict[str, str]]  # [{"original": "wnt", "corrected": "want"}]
    sub_questions: List[str]  # If multi-question detected
    has_multi_questions: bool
    confidence: float  # How confident we are in the preprocessing


class QueryPreprocessor:
    """
    Preprocesses user queries to improve agent understanding.
    
    Steps:
    1. Detect and split multi-questions
    2. Correct common typos (preserving technical terms)
    3. Normalize spacing and capitalization
    """
    
    # Common misspellings in guitar pedal context
    TYPO_CORRECTIONS = {
        # Common typos
        "wnt": "want",
        "wan": "want",
        "wnat": "want",
        "bbuy": "buy",
        "buuy": "buy",
        "byu": "buy",
        "byy": "buy",
        "connnect": "connect",
        "connct": "connect",
        "conect": "connect",
        "conectt": "connect",
        "too": "to",  # Context-dependent, but often wrong in "connect too"
        "tto": "to",
        "teh": "the",
        "thee": "the",
        "taht": "that",
        "thta": "that",
        "hwo": "how",
        "hww": "how",
        "hoow": "how",
        "hriw": "how",  # Severe typo from user query
        "whta": "what",
        "waht": "what",
        "wht": "what",
        "cabel": "cable",
        "cabl": "cable",
        "cabble": "cable",
        "pric": "price",
        "priice": "price",
        "prce": "price",
        "efect": "effect",
        "effct": "effect",
        "efects": "effects",
        "efectts": "effects",
        "peadl": "pedal",
        "pedla": "pedal",
        "peddal": "pedal",
        "pedaal": "pedal",
        "ampp": "amp",
        "ammp": "amp",
        "guitr": "guitar",
        "gutar": "guitar",
        "guitarr": "guitar",
        "seeting": "setting",
        "seting": "setting",
        "settng": "setting",
        "manuall": "manual",
        "manul": "manual",
        "mannual": "manual",
        "turn": "turn",  # Keep correct
        "turnn": "turn",
        "trn": "turn",
        "trun": "turn",
        "on": "on",  # Keep correct
        "onn": "on",
        "oon": "on",
    }
    
    # Technical terms that should NEVER be corrected
    TECHNICAL_TERMS = [
        r'\b[A-Z]{2,}-?\d+[A-Z]?\b',  # Boss DS-1, MXR M234, etc.
        r'\bUSB\b',
        r'\bMIDI\b',
        r'\bXLR\b',
        r'\bTRS\b',
        r'\b1/4"\b',
        r'\bkHz\b',
        r'\bdB\b',
        r'\bHz\b',
        r'\bV\b',
        r'\bmA\b',
        r'\bΩ\b',
    ]
    
    # Patterns for multi-question detection
    MULTI_QUESTION_PATTERNS = [
        r'\band\s+(?:how|what|where|when|why|who|can|does|is|are)',  # "buy and how"
        r'\b(?:also|plus)\s*,?\s*(?:how|what|where)',  # "also what"
        r'\?\s*(?:how|what|where|when|why)',  # "? what"
        r',\s*(?:and\s+)?(?:how|what|where)',  # ", and how"
    ]
    
    def __init__(self):
        """Initialize query preprocessor."""
        # Compile technical term patterns for efficiency
        self.technical_patterns = [re.compile(pattern, re.IGNORECASE) 
                                   for pattern in self.TECHNICAL_TERMS]
    
    def preprocess(self, query: str) -> PreprocessingResult:
        """
        Preprocess a query.
        
        Args:
            query: Raw user query
        
        Returns:
            PreprocessingResult with normalized query and metadata
        """
        logger.info(f"[PREPROCESSOR] Original query: {query[:100]}")
        
        original_query = query
        
        # Step 1: Detect multi-questions BEFORE typo correction
        # (We want to preserve the structure for splitting)
        sub_questions, has_multi = self._detect_multi_questions(query)
        
        # Step 2: Correct typos
        normalized_query, typos = self._correct_typos(query)
        
        # Step 3: Normalize spacing and capitalization
        normalized_query = self._normalize_spacing(normalized_query)
        
        # Step 4: Re-split multi-questions with corrected text
        if has_multi:
            sub_questions = self._split_questions(normalized_query)
        
        # Calculate confidence
        confidence = self._calculate_confidence(
            original_query, 
            normalized_query, 
            typos,
            has_multi
        )
        
        result = PreprocessingResult(
            normalized_query=normalized_query,
            original_query=original_query,
            typos_corrected=typos,
            sub_questions=sub_questions,
            has_multi_questions=has_multi,
            confidence=confidence
        )
        
        logger.info(
            f"[PREPROCESSOR] Normalized: {result.normalized_query[:100]} "
            f"| Typos: {len(typos)} | Multi: {has_multi} | Confidence: {confidence:.2f}"
        )
        
        return result
    
    def _detect_multi_questions(self, query: str) -> Tuple[List[str], bool]:
        """
        Detect if query contains multiple questions.
        
        Args:
            query: User query
        
        Returns:
            (sub_questions, has_multi_questions)
        """
        query_lower = query.lower()
        
        # Check for multi-question patterns
        for pattern in self.MULTI_QUESTION_PATTERNS:
            if re.search(pattern, query_lower):
                # Found multi-question pattern
                sub_questions = self._split_questions(query)
                return sub_questions, len(sub_questions) > 1
        
        # No multi-question detected
        return [query], False
    
    def _split_questions(self, query: str) -> List[str]:
        """
        Split a multi-question query into sub-questions.
        
        Strategy:
        - Split on "and how/what/where/etc."
        - Split on "?" followed by new question
        - Split on ", and"
        
        Args:
            query: Query to split
        
        Returns:
            List of sub-questions
        """
        # Try splitting on common separators
        separators = [
            r'\s+and\s+(?=how|what|where|when|why|can|does|is|are)',
            r'\?\s+(?=how|what|where|when|why)',
            r',\s*(?:and\s+)?(?=how|what|where)',
        ]
        
        parts = [query]
        for separator in separators:
            new_parts = []
            for part in parts:
                split_parts = re.split(separator, part, flags=re.IGNORECASE)
                new_parts.extend(split_parts)
            parts = new_parts
        
        # Clean up parts
        sub_questions = []
        for part in parts:
            cleaned = part.strip().strip('.,;')
            if cleaned and len(cleaned) > 3:  # Ignore very short fragments
                sub_questions.append(cleaned)
        
        # If we couldn't split meaningfully, return original
        if len(sub_questions) <= 1:
            return [query]
        
        logger.info(f"[PREPROCESSOR] Split into {len(sub_questions)} sub-questions: {sub_questions}")
        return sub_questions
    
    def _correct_typos(self, query: str) -> Tuple[str, List[Dict[str, str]]]:
        """
        Correct common typos while preserving technical terms.
        
        Args:
            query: Query to correct
        
        Returns:
            (corrected_query, list of corrections made)
        """
        typos_corrected = []
        
        # First pass: clean up malformed words with special characters
        query = self._clean_special_chars(query)
        
        words = query.split()
        corrected_words = []
        
        for word in words:
            # Preserve technical terms
            if self._is_technical_term(word):
                corrected_words.append(word)
                continue
            
            # Check for typos (case-insensitive)
            word_lower = word.lower().strip('.,!?;:')
            
            if word_lower in self.TYPO_CORRECTIONS:
                corrected = self.TYPO_CORRECTIONS[word_lower]
                
                # Preserve original capitalization pattern
                if word[0].isupper():
                    corrected = corrected.capitalize()
                
                # Preserve trailing punctuation
                trailing = ''
                if word[-1] in '.,!?;:':
                    trailing = word[-1]
                
                corrected_word = corrected + trailing
                corrected_words.append(corrected_word)
                
                typos_corrected.append({
                    "original": word,
                    "corrected": corrected_word,
                    "position": len(corrected_words) - 1
                })
                
                logger.debug(f"[PREPROCESSOR] Typo corrected: '{word}' → '{corrected_word}'")
            else:
                corrected_words.append(word)
        
        corrected_query = ' '.join(corrected_words)
        return corrected_query, typos_corrected
    
    def _is_technical_term(self, word: str) -> bool:
        """
        Check if a word is a technical term that shouldn't be corrected.
        
        Args:
            word: Word to check
        
        Returns:
            True if technical term
        """
        for pattern in self.technical_patterns:
            if pattern.match(word):
                return True
        return False
    
    def _clean_special_chars(self, query: str) -> str:
        """
        Clean up malformed words with special characters.
        
        Handles cases like "r=th=urn" → "rthurn" which then can be corrected.
        
        Args:
            query: Query to clean
        
        Returns:
            Cleaned query
        """
        import re
        
        # Replace = with empty string (common typing error)
        query = query.replace('=', '')
        
        # Replace multiple consecutive punctuation with single
        query = re.sub(r'([.,!?;:]){2,}', r'\1', query)
        
        # Fix doubled letters that are clearly errors (3+ repeats)
        # e.g., "helllllo" → "hello"
        query = re.sub(r'(\w)\1{2,}', r'\1\1', query)
        
        return query
    
    def _normalize_spacing(self, query: str) -> str:
        """
        Normalize spacing and capitalization.
        
        Args:
            query: Query to normalize
        
        Returns:
            Normalized query
        """
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', query)
        
        # Trim
        normalized = normalized.strip()
        
        return normalized
    
    def _calculate_confidence(
        self, 
        original: str, 
        normalized: str, 
        typos: List[Dict[str, str]],
        has_multi: bool
    ) -> float:
        """
        Calculate confidence in preprocessing.
        
        High confidence if:
        - Few typos corrected (query was already clean)
        - OR many typos but clear patterns
        - Multi-question detection is unambiguous
        
        Args:
            original: Original query
            normalized: Normalized query
            typos: List of typo corrections
            has_multi: Whether multi-questions detected
        
        Returns:
            Confidence score 0.0-1.0
        """
        base_confidence = 0.85
        
        # Penalize for many typos (less confident in understanding)
        if len(typos) > 5:
            base_confidence -= 0.15
        elif len(typos) > 3:
            base_confidence -= 0.10
        elif len(typos) > 1:
            base_confidence -= 0.05
        
        # Slight penalty for multi-question (harder to parse)
        if has_multi:
            base_confidence -= 0.05
        
        # Boost if query is very different after normalization (we fixed a lot)
        if len(typos) >= 2 and original != normalized:
            base_confidence += 0.05  # We likely helped significantly
        
        return max(0.5, min(1.0, base_confidence))


# CONVENIENCE FUNCTIONS

def preprocess_query(query: str) -> PreprocessingResult:
    """
    Convenience function to preprocess a query.
    
    Args:
        query: Raw user query
    
    Returns:
        PreprocessingResult
    """
    preprocessor = QueryPreprocessor()
    return preprocessor.preprocess(query)
