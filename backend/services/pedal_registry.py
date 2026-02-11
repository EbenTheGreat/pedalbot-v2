"""
Pedal Registry Service: Resolves user-facing pedal names to system namespaces.

This is the missing architectural layer that decouples:
- User input (flexible, fuzzy): "Helix", "helix", "Line 6 Helix"
- System namespace (rigid, exact): "manual_helix_3.80_owner's_manual___english"

Design Principles:
1. User-facing = flexible (normalize, fuzzy match)
2. System-facing = exact (namespace, manual_id)
3. Multi-effects pedals get special treatment for retrieval
"""

from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class PedalType(str, Enum):
    """Types of pedals for special routing logic."""
    SINGLE_EFFECT = "single_effect"     # Boss DS-1, etc.
    MULTI_EFFECTS = "multi_effects"     # Helix, GT-10, etc.
    AMP_MODELER = "amp_modeler"         # Kemper, Axe-FX
    UNKNOWN = "unknown"


@dataclass
class PedalInfo:
    """Resolved pedal information."""
    display_name: str           # User-friendly name
    namespace: str              # Pinecone namespace
    manual_id: str              # MongoDB manual_id
    pedal_type: PedalType       # Type for routing decisions
    manufacturer: Optional[str] = None
    canonical_name: Optional[str] = None  # Market-safe product name (e.g., "Boss GT-1")
    aliases: List[str] = None   # Alternative names for matching
    
    def __post_init__(self):
        if self.aliases is None:
            self.aliases = []


class PedalRegistry:
    """
    Registry service for pedal name → namespace resolution.
    
    Loads from MongoDB on demand and caches results.
    Provides fuzzy matching for user input flexibility.
    """
    
    # Static mapping for known multi-effects units
    # These require retrieval regardless of intent
    KNOWN_MULTI_EFFECTS = {
        "helix": PedalType.MULTI_EFFECTS,
        "hx stomp": PedalType.MULTI_EFFECTS,
        "pod go": PedalType.MULTI_EFFECTS,
        "gt-10": PedalType.MULTI_EFFECTS,
        "gt-1000": PedalType.MULTI_EFFECTS,
        "axe-fx": PedalType.AMP_MODELER,
        "kemper": PedalType.AMP_MODELER,
        "quad cortex": PedalType.AMP_MODELER,
        "headrush": PedalType.MULTI_EFFECTS,
        "zoom": PedalType.MULTI_EFFECTS,
    }
    
    def __init__(self):
        self._cache: Dict[str, PedalInfo] = {}  # Map normalized name → Info
        self._all_pedals: List[Dict[str, Any]] = []
        self._loaded = False
    
    async def load_from_db(self) -> None:
        """Load all pedals from MongoDB into cache."""
        try:
            from backend.db.mongodb import MongoDB
            db = MongoDB.get_database()
            
            cursor = db.manuals.find({"status": "completed"})
            manuals = await cursor.to_list(length=100)
            
            self._all_pedals = manuals
            self._cache.clear()
            
            for manual in manuals:
                pedal_name = manual.get("pedal_name", "")
                namespace = manual.get("pinecone_namespace", "")
                manual_id = manual.get("manual_id", "")
                manufacturer = manual.get("manufacturer")
                
                if not namespace:
                    continue
                
                # Determine pedal type
                pedal_type = self._infer_pedal_type(pedal_name)
                
                # Create pedal info
                canonical = manual.get("canonical_name") or self._extract_canonical_name(pedal_name, manufacturer)
                info = PedalInfo(
                    display_name=pedal_name,
                    namespace=namespace,
                    manual_id=manual_id,
                    pedal_type=pedal_type,
                    manufacturer=manufacturer,
                    canonical_name=canonical,
                    aliases=self._generate_aliases(pedal_name)
                )
                
                # Cache by normalized name
                normalized = self._normalize(pedal_name)
                self._cache[normalized] = info
                
                # Also cache aliases
                for alias in info.aliases:
                    alias_normalized = self._normalize(alias)
                    if alias_normalized not in self._cache:
                        self._cache[alias_normalized] = info
            
            self._loaded = True
            logger.info(f"PedalRegistry loaded {len(manuals)} pedals")
            
        except Exception as e:
            logger.error(f"Failed to load pedal registry: {e}")
            raise
    
    async def resolve(self, user_input: str) -> Optional[PedalInfo]:
        """
        Resolve user input to pedal info.
        
        Args:
            user_input: User-provided pedal name (can be fuzzy)
            
        Returns:
            PedalInfo if found, None otherwise
        """
        if not self._loaded:
            await self.load_from_db()
        
        if not user_input:
            return None
        
        normalized = self._normalize(user_input)
        
        # Try exact match first
        if normalized in self._cache:
            logger.info(f"Resolved '{user_input}' → '{self._cache[normalized].namespace}' (exact)")
            return self._cache[normalized]
        
        # Try prefix match (e.g., "Helix" matches "Helix 3.80 Owner's Manual")
        for key, info in self._cache.items():
            if key.startswith(normalized) or normalized.startswith(key):
                logger.info(f"Resolved '{user_input}' → '{info.namespace}' (prefix)")
                return info
        
        # Try substring match (e.g., "Helix" anywhere in name)
        for key, info in self._cache.items():
            if normalized in key or key in normalized:
                logger.info(f"Resolved '{user_input}' → '{info.namespace}' (substring)")
                return info
        
        # Try fuzzy word match
        user_words = set(normalized.split())
        for key, info in self._cache.items():
            key_words = set(key.split())
            # If any significant word matches
            common_words = user_words & key_words
            # Filter out common stopwords
            common_words = {w for w in common_words if len(w) > 2}
            if common_words:
                logger.info(f"Resolved '{user_input}' → '{info.namespace}' (word match: {common_words})")
                return info
        
        logger.warning(f"Failed to resolve pedal: '{user_input}'")
        return None
    
    def requires_retrieval(self, pedal_info: PedalInfo) -> bool:
        """
        Determine if this pedal requires retrieval regardless of intent.
        
        Multi-effects processors and amp modelers ALWAYS need retrieval
        because their features (signal chain, blocks, routing) are 
        documented in the manual.
        """
        return pedal_info.pedal_type in (PedalType.MULTI_EFFECTS, PedalType.AMP_MODELER)
    
    async def list_all(self) -> List[PedalInfo]:
        """List all available pedals."""
        if not self._loaded:
            await self.load_from_db()
        
        # Return unique pedals (not aliases)
        seen = set()
        result = []
        for info in self._cache.values():
            if info.namespace not in seen:
                seen.add(info.namespace)
                result.append(info)
        return result
    
    def _normalize(self, name: str) -> str:
        """
        Normalize pedal name for matching.
        
        Transforms:
        - "Helix 3.80 Owner's Manual - English" → "helix 380 owners manual english"
        - "Boss DS-1" → "boss ds1"
        """
        if not name:
            return ""
        
        # Lowercase
        normalized = name.lower()
        
        # Remove special characters, keep alphanumeric and spaces
        normalized = re.sub(r"[^a-z0-9\s]", "", normalized)
        
        # Collapse multiple spaces
        normalized = re.sub(r"\s+", " ", normalized).strip()
        
        return normalized
    
    def _generate_aliases(self, pedal_name: str) -> List[str]:
        """
        Generate alternative names for matching.
        
        Example: "Helix 3.80 Owner's Manual - English"
        Aliases: ["Helix", "Helix 3.80", "Line 6 Helix"]
        """
        aliases = []
        
        # Split by common separators
        parts = re.split(r"[-_\s]+", pedal_name)
        
        # First word is often the key identifier
        if parts:
            aliases.append(parts[0])
        
        # First two words
        if len(parts) >= 2:
            aliases.append(f"{parts[0]} {parts[1]}")
        
        # Remove common suffixes like "manual", "owner's", "english"
        cleaned = re.sub(
            r"\b(manual|owner'?s|english|pdf|user|guide|version|v\d+)\b",
            "",
            pedal_name.lower()
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned and cleaned != self._normalize(pedal_name):
            aliases.append(cleaned)
        
        return list(set(aliases))  # Deduplicate
    
    def _infer_pedal_type(self, pedal_name: str) -> PedalType:
        """Infer pedal type from name."""
        normalized = self._normalize(pedal_name)
        
        # Check against known multi-effects
        for keyword, ptype in self.KNOWN_MULTI_EFFECTS.items():
            if keyword in normalized:
                return ptype
        
        # Heuristics for multi-effects
        multi_keywords = ["multi", "processor", "workstation", "floor", "modeler"]
        if any(kw in normalized for kw in multi_keywords):
            return PedalType.MULTI_EFFECTS
        
        return PedalType.SINGLE_EFFECT
    
    def _extract_canonical_name(self, pedal_name: str, manufacturer: Optional[str]) -> str:
        """
        Extract canonical product name for market queries.
        
        Examples:
        - "GT-1 eng03 W" + manufacturer="Boss" → "Boss GT-1"
        - "Helix 3.80 Owner's Manual" + manufacturer="Line 6" → "Line 6 Helix"
        - "DS-1 Distortion" + None → "DS-1"
        
        Args:
            pedal_name: Raw pedal name from filename or manual
            manufacturer: Manufacturer if known
            
        Returns:
            Clean canonical name for market APIs
        """
        # Remove common suffixes
        cleaned = re.sub(
            r"\b(manual|owner'?s|eng\d+|english|pdf|user|guide|version|v\d+\.\d+)\b",
            "",
            pedal_name,
            flags=re.IGNORECASE
        )
        
        # Remove extra whitespace and special chars
        cleaned = re.sub(r"[_]+", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        # If we have manufacturer, prepend it if not already present
        if manufacturer:
            manufacturer_normalized = manufacturer.strip()
            if manufacturer_normalized.lower() not in cleaned.lower():
                cleaned = f"{manufacturer_normalized} {cleaned}"
        
        return cleaned or pedal_name  # Fallback to original if cleaning fails


# Global singleton instance
_registry: Optional[PedalRegistry] = None


async def get_pedal_registry() -> PedalRegistry:
    """Get or create the global pedal registry."""
    global _registry
    
    if _registry is None:
        _registry = PedalRegistry()
        await _registry.load_from_db()
    
    return _registry


async def resolve_pedal(user_input: str) -> Optional[PedalInfo]:
    """
    Convenience function to resolve a pedal name.
    
    Args:
        user_input: User-provided pedal name
        
    Returns:
        PedalInfo if found, None otherwise
    """
    registry = await get_pedal_registry()
    return await registry.resolve(user_input)
