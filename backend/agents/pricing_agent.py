"""
Pricing Agent: Fetches and analyzes pedal market prices.

Integrates with Reverb API for real-time pricing data.
"""
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta, UTC
import statistics
import httpx

from backend.state import AgentState

logger = logging.getLogger(__name__)

class PricingAgent:
    """
    Fetches current market prices for pedals from Reverb.
    
    Features:
    - Real-time pricing from Reverb API
    - Price statistics (avg, min, max, median)
    - Condition-based filtering
    - 24-hour caching in MongoDB
    """

    def __init__(self,
                reverb_api_key: Optional[str] = None,
                cache_ttl_hours: int = 24,):
        """
        Initialize pricing agent.
        
        Args:
            reverb_api_key: Reverb API key (optional)
            cache_ttl_hours: Cache duration in hours
        """

        self.api_key = reverb_api_key
        self.cache_ttl = cache_ttl_hours
        self.base_url= "https://api.reverb.com/api"

    # Known products for fallback resolution when registry fails
    KNOWN_PRODUCTS_MARKET = {
        'gt-1': 'Boss GT-1',
        'gt1': 'Boss GT-1',
        'gt 1': 'Boss GT-1',
        'gt-10': 'Boss GT-10',
        'gt-100': 'Boss GT-100',
        'gt-1000': 'Boss GT-1000',
        'ds-1': 'Boss DS-1',
        'ds1': 'Boss DS-1',
        'ds 1': 'Boss DS-1',
        'me-80': 'Boss ME-80',
        'mg-30': 'NUX MG-30',
        'mg30': 'NUX MG-30',
        'mg 30': 'NUX MG-30',
        'helix': 'Line 6 Helix',
        'hx stomp': 'Line 6 HX Stomp',
        'pod go': 'Line 6 POD Go',
        'ts9': 'Ibanez TS9',
        'ts-9': 'Ibanez TS9',
        'tube screamer': 'Ibanez Tube Screamer',
        'timeline': 'Strymon Timeline',
        'bigsky': 'Strymon BigSky',
    }

    async def _resolve_market_name(self, pedal_name: str) -> str:
        """
        Resolve pedal_name to canonical market-safe name.
        
        This prevents queries like "GT-1 eng03 W" → Reverb,
        and instead sends "Boss GT-1".
        
        Args:
            pedal_name: Original pedal name from state
            
        Returns:
            Canonical market name for API queries
        """
        import re
        
        # First: try to resolve via pedal registry (has canonical_name from DB)
        try:
            from backend.services.pedal_registry import resolve_pedal
            
            pedal_info = await resolve_pedal(pedal_name)
            
            if pedal_info and pedal_info.canonical_name:
                logger.info(f"Registry resolved: '{pedal_name}' → '{pedal_info.canonical_name}'")
                return pedal_info.canonical_name
            
        except Exception as e:
            logger.warning(f"Could not resolve pedal identity: {e}")
        
        # Second: clean up the name ourselves
        cleaned = pedal_name
        
        # Remove common filename artifacts (case-insensitive)
        patterns_to_remove = [
            r'\s+eng\d*',              # eng, eng03, etc
            r'\s+[a-z]{2}\d+$',        # language codes like fr01, de02
            r'\s+w$',                   # trailing W
            r'\s+\d+\.\d+',            # version numbers like 3.80
            r"\s*owner'?s?\s*manual",  # owner's manual
            r'\s*user\s*manual',       # user manual  
            r'\s*manual$',             # trailing manual
            r'\s*english$',            # trailing english
            r'\s*\(\d+\)$',            # duplicate markers like (1)
            r'_+',                      # underscores → spaces
        ]
        
        for pattern in patterns_to_remove:
            cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
        
        # Normalize whitespace
        cleaned = ' '.join(cleaned.split()).strip()
        
        # Fix model number formatting: "GT 1" → "GT-1", "DS 1" → "DS-1"
        cleaned = re.sub(r'\b([A-Za-z]+)\s+(\d+)\b', r'\1-\2', cleaned)
        
        # Third: check against known products mapping
        cleaned_lower = cleaned.lower()
        
        # Direct match
        if cleaned_lower in self.KNOWN_PRODUCTS_MARKET:
            canonical = self.KNOWN_PRODUCTS_MARKET[cleaned_lower]
            logger.info(f"Known product matched: '{pedal_name}' → '{canonical}'")
            return canonical
        
        # Check if any known product model is contained in the cleaned name
        for model, canonical in self.KNOWN_PRODUCTS_MARKET.items():
            # Match as word boundary
            pattern = rf'\b{re.escape(model)}\b'
            if re.search(pattern, cleaned_lower):
                logger.info(f"Known product model found: '{pedal_name}' → '{canonical}'")
                return canonical
        
        if cleaned != pedal_name:
            logger.info(f"Cleaned market query: '{pedal_name}' → '{cleaned}'")
        
        return cleaned


    async def get_pricing(self, state: AgentState) -> AgentState:
        """
        Get pricing information for a pedal.
        
        Args:
            state: Agent state with pedal_name
        
        Returns:
            Updated state with price_info
        """
        logger.info(f"Pricing agent: fetching prices for {state.pedal_name}")

        try:
            # Resolve pedal identity for market query
            market_query_name = await self._resolve_market_name(state.pedal_name)
            logger.info(f"Market query resolved: '{state.pedal_name}' → '{market_query_name}'")
            
            # Check cache first (from MongoDB) - use original pedal_name for cache key
            cached_price = await self._get_cached_price(state.pedal_name)
            if cached_price:
                logger.info(f"Cache hit for {state.pedal_name}")
                state.price_info = cached_price
                state.agent_path.append("pricing_agent_cached")
                return state
            
            # Fetch from Reverb API using canonical market name
            if self.api_key:
                price_data = await self._fetch_from_reverb(market_query_name)
            else:
                # Fallback
                logger.warning("No reverb Api key - using mock data")
                price_data = self._get_mock_pricing(market_query_name)
            
            # Store original pedal_name in results for proper display
            price_data["display_name"] = state.pedal_name
            # Cache result
            await self._cache_price(state.pedal_name, price_data)
            state.price_info = price_data
            state.agent_path.append("pricing_agent")
            
            # Generate raw_answer for quality check
            state.raw_answer = self._format_pricing_answer(price_data)
            
            logger.info(
            f" Fetched pricing: ${price_data['avg_price']:.2f} avg "
            f"({price_data['total_listings']} listings)"
            )
        
            return state
    
        except Exception as e:
            logger.error(f"Pricing agent failed: {e}")
            state.error = f"Pricing error: {str(e)}"
            state.price_info = {
                "error": "Unable to fetch pricing data",
                "pedal_name": state.pedal_name
            }
            return state
            
    async def _fetch_from_reverb(self, pedal_name: str) -> Dict[str, Any]:
        """
        Fetch pricing from Reverb API.
        Args:
            pedal_name: Name of pedal
        Returns:
            Price statistics and listings
        """
        import httpx
        import asyncio
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/hal+json",
            "Accept-Version": "3.0"
        }
        
        def _sync_fetch():
            """Sync fetch wrapper - works around Windows async DNS issues."""
            with httpx.Client(timeout=30.0) as client:
                response = client.get(
                    f"{self.base_url}/listings",
                    headers=headers,
                    params={
                        "query": pedal_name,
                        "item_region": "US",
                        "category": "effects-and-pedals",
                        "per_page": 50,
                        "state": "live"
                    }
                )
                response.raise_for_status()
                return response.json()
        
        try:
            logger.info(f"Fetching Reverb listings for: {pedal_name}")
            # Run sync client in thread pool to avoid blocking event loop
            data = await asyncio.to_thread(_sync_fetch)
            logger.info(f"Reverb API returned {len(data.get('listings', []))} listings")
        except httpx.ConnectError as e:
            logger.error(f"Reverb API connection error: {e}")
            raise ConnectionError(f"Cannot connect to Reverb API: {e}")
        except httpx.TimeoutException as e:
            logger.error(f"Reverb API timeout: {e}")
            raise TimeoutError(f"Reverb API request timed out: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"Reverb API HTTP error: {e.response.status_code}")
            raise
        # Get listings
        listings = data.get("listings", [])
        if not listings:
            return {
            "pedal_name": pedal_name,
            "avg_price": 0.0,
            "min_price": 0.0,
            "max_price": 0.0,
            "median_price": 0.0,
            "total_listings": 0,
            "listings": [],
            "source": "reverb",
            "updated_at": datetime.now(UTC)
            }
        
        # Parse listings
        parsed_listings = []
        prices = []
        for listing in listings:
            price = listing.get("price", {}).get("amount")
            if not price:
                continue
            prices.append(float(price))
            parsed_listings.append({
            "listing_id": listing.get("id"),
            "price_usd": float(price),
            "condition": listing.get("condition", {}).get("display_name", "unknown"),
            "url": listing.get("_links", {}).get("web", {}).get("href", ""),
            "seller_name": listing.get("seller", {}).get("username", ""),
            "shipping_usd": float(listing.get("shipping", {}).get("local_amount", 0)),
            "listed_at": datetime.now(UTC)
        })
            
        # Calculate statistics
        return {
        "pedal_name": pedal_name,
        "avg_price": statistics.mean(prices) if prices else 0.0,
        "min_price": min(prices) if prices else 0.0,
        "max_price": max(prices) if prices else 0.0,
        "median_price": statistics.median(prices) if prices else 0.0,
        "total_listings": len(parsed_listings),
        "listings": parsed_listings[:10],  # Top 10
        "source": "reverb",
        "updated_at": datetime.now(UTC)
    }
    
    

    def _get_mock_pricing(self, pedal_name: str) -> Dict[str, Any]:
        """
        Generate mock pricing data for testing.
        
        Args:
            pedal_name: Pedal name
        
        Returns:
            Mock price data
        """

        # Mock prices for common pedals
        mock_data = {
            "Boss DS-1": {"avg": 54.99, "min": 35.00, "max": 89.99, "listings": 127},
            "Ibanez TS9": {"avg": 89.99, "min": 60.00, "max": 149.99, "listings": 89},
            "MXR Phase 90": {"avg": 79.99, "min": 55.00, "max": 120.00, "listings": 64},
            "Electro-Harmonix Big Muff": {"avg": 89.99, "min": 65.00, "max": 150.00, "listings": 102},
        }

        # Default to generic pricing if pedal not in mock data
        prices = mock_data.get(pedal_name, {"avg": 99.99, "min": 50.00, "max": 200.00, "listings": 50})
        
        return {
            "pedal_name": pedal_name,
            "avg_price": prices["avg"],
            "min_price": prices["min"],
            "max_price": prices["max"],
            "median_price": prices["avg"],
            "total_listings": prices["listings"],
            "listings": [],
            "source": "mock",
            "updated_at": datetime.now(UTC)
        }
    
    async def _get_cached_price(self, pedal_name: str) -> Optional[Dict[str, Any]]:
        """
        Get cached price from MongoDB.
        
        Args:
            pedal_name: Pedal name
        
        Returns:
            Cached price data or None
        """

        from backend.db.mongodb import MongoDB

        db = MongoDB.get_database()

        # Find cached price
        cached = await db.pricing.find_one({"pedal_name": pedal_name})

        if not cached:
            return None 

        # Check if cache is still valid (24h TTL)
        updated_at = cached.get("updated_at")
        if updated_at:
            # Ensure updated_at is offset-aware (UTC)
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=UTC)
                
            if datetime.now(UTC) - updated_at < timedelta(hours=self.cache_ttl):
                return cached
        
        return None
    
    async def _cache_price(self, pedal_name: str, price_data: Dict[str, Any]) -> None:
        """
        Cache price in MongoDB.
        
        Args:
            pedal_name: Pedal name
            price_data: Price data to cache
        """

        from backend.db.mongodb import MongoDB
        db = MongoDB.get_database()

        # Upsert (update or insert)
        await db.pricing.update_one(
            {"pedal_name": pedal_name},
            {"$set": price_data},
            upsert=True
        )

    def _format_pricing_answer(self, price_data: Dict[str, Any]) -> str:
        """Format pricing data into a human-readable answer."""
        if not price_data or price_data.get("error"):
            return "I couldn't fetch pricing data at this time."
        
        pedal = price_data.get("pedal_name", "this pedal")
        avg = price_data.get("avg_price", 0)
        min_p = price_data.get("min_price", 0)
        max_p = price_data.get("max_price", 0)
        count = price_data.get("total_listings", 0)
        
        return (
            f"Based on {count} active listings on Reverb, the **{pedal}** "
            f"currently sells for an average of **${avg:.2f}**. "
            f"Prices range from ${min_p:.2f} to ${max_p:.2f}, depending on condition."
        )


# HELPER FUNCTIONS
def format_price_summary(price_info: Dict[str, Any]) -> str:
    """
    Format price info into human-readable summary.
    
    Args:
        price_info: Price data from pricing agent
    
    Returns:
        Formatted string
    """

    if not price_info or price_info.get("error"):
        return "Pricing data unavailable"
    
    summary = f"**{price_info['pedal_name']} - Market Pricing**\n\n"
    summary += f"• Average: ${price_info['avg_price']:.2f}\n"
    summary += f"• Range: ${price_info['min_price']:.2f} - ${price_info['max_price']:.2f}\n"
    summary += f"• Median: ${price_info['median_price']:.2f}\n"
    summary += f"• Active listings: {price_info['total_listings']}\n"
    summary += f"\n*Updated: {price_info['updated_at'].strftime('%Y-%m-%d %H:%M')}*"
    
    return summary

def get_price_recomendation(price_info: Dict[str, Any], target_price: float) -> str:
    """
    Provide buying recommendation based on market data.
    
    Args:
        price_info: Price data
        target_price: Price user is considering
    
    Returns:
        Recommendation text
    """
    if not price_info or price_info.get("error"):
        return "Unable to provide recommendation without pricing data."
    
    avg = price_info['avg_price']
    min_price = price_info['min_price']
    max_price = price_info['max_price']
    
    if target_price < min_price:
        return f"Excellent deal! That's below the minimum market price (${min_price:.2f})."
    elif target_price < avg * 0.9:
        return f"Good deal! That's below average market price (${avg:.2f})."
    elif target_price <= avg * 1.1:
        return f"Fair price. Close to market average (${avg:.2f})."
    elif target_price <= max_price:
        return f"Above average. Consider negotiating closer to ${avg:.2f}."
    else:
        return f"❌ Overpriced. Market max is ${max_price:.2f}, average is ${avg:.2f}."
    

async def get_pricing_with_cache(pedal_name: str, agent: PricingAgent,) -> Dict[str, Any]:
    """
    Convenience function to get pricing with automatic caching.
    
    Args:
        pedal_name: Pedal name
        agent: PricingAgent instance
    
    Returns:
        Price data
    """

    from backend.state import AgentState
    from datetime import date, UTC

    state = AgentState(
        user_id="temp_user",
        conversation_id="temp_conv",
        query="temp_query",
        pedal_name=pedal_name,
        created_at=datetime.now(UTC)
    )

    state = await agent.get_pricing(state)

    return state.price_info or {}
