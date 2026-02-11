"""
Pricing worker for background price updates.

Refreshes pricing data from Reverb API.
"""
from celery import Task
import logging
import asyncio
from backend.workers.celery_app import BaseTask, app

logger = logging.getLogger(__name__)

# REFRESH PRICING TASK

@app.task(name="refresh_pricing", base=BaseTask)
def refresh_pricing_task(pedal_name: str) -> dict:
    """
    Refresh pricing for a single pedal.
    
    Args:
        pedal_name: Pedal name
    
    Returns:
        Updated pricing data
    """
    logger.info(f"Refreshing pricing: {pedal_name}")

    async def runner():
        from backend.db.mongodb import MongoDB
        from backend.config.config import settings

        # 🔑 Initialize MongoDB FIRST
        await MongoDB.connect(
            uri=settings.MONGODB_URI,
            db_name=settings.MONGODB_DB_NAME
        )

        try:
            result = await _refresh_pricing_async(pedal_name)
            return result
        except Exception as e:
            logger.error(f"Pricing refresh failed for {pedal_name}: {e}", exc_info=True)
            raise
        finally:
            await MongoDB.close()

    try:
        return asyncio.run(runner())
    except Exception as e:
        # Log error and re-raise for Celery to handle
        logger.error(f"Pricing task failed: {e}", exc_info=True)
        raise
    

async def _refresh_pricing_async(pedal_name: str) -> dict:
    """
    Async pricing refresh logic.
    
    Note: MongoDB connection is managed by the parent task runner.
    
    Args:
        pedal_name: Pedal name
    
    Returns:
        Updated pricing data
    """
    from backend.db.mongodb import MongoDB
    from backend.agents.pricing_agent import PricingAgent
    from backend.state import AgentState
    from backend.config.config import settings
    from datetime import datetime, UTC
    
    # Initialize pricing agent
    pricing_agent = PricingAgent(
        reverb_api_key=settings.REVERB_API_KEY,
        cache_ttl_hours=24
    )

    # Create State
    state = AgentState(
        user_id="system",
        conversation_id="pricing_refresh",
        query="refresh_pricing",
        pedal_name=pedal_name,
        created_at=datetime.now(UTC)
    )

    # Get pricing (bypasses cache by clearing it first)
    db = MongoDB.get_database()
    await db.pricing.delete_one({"pedal_name": pedal_name})

    state = await pricing_agent.get_pricing(state)

    if not state.price_info:
        raise RuntimeError(f"No pricing data returned for {pedal_name}")
    
    logger.info(
        f"Pricing refreshed: {pedal_name} - "
        f"${state.price_info['avg_price']:.2f} avg"
    )
    
    return state.price_info


# REFRESH ALL PRICING TASK
@app.task(name='refresh_all_pricing', base=BaseTask)
def refresh_all_pricing_task() -> dict:
    """
    Refresh pricing for all pedals in the database.
    
    Runs daily via Celery Beat.
    
    Returns:
        Refresh stats
    """
    logger.info("Starting bulk pricing refresh")

    result = asyncio.run(_refresh_all_pricing_async())

    logger.info(
        f"Bulk refresh complete: {result['refreshed']}/{result['total']} pedals"
    )
    
    return result


async def _refresh_all_pricing_async() -> dict:
    """Async bulk pricing refresh logic."""
    from backend.db.mongodb import MongoDB
    from backend.config.config import settings
    from celery import group, signature

    await MongoDB.connect(
        uri=settings.MONGODB_URI,
        db_name=settings.MONGODB_DB_NAME
    )

    db = MongoDB.get_database()

    try:
        # Get all unique pedal names from manuals
        manuals = await db.manuals.find(
            {"status": "completed"},
            {"pedal_name": 1}
        ).to_list(length=1000)


        pedal_names = list(set(m["pedal_name"] for m in manuals))
        
        logger.info(f"Found {len(pedal_names)} unique pedals to refresh")

        # Create parallel refresh tasks
        job = group(
            signature("refresh_pricing", args=(pedal_name,))
            for pedal_name in pedal_names
        )
        
        # Execute (don't wait - fire and forget)
        job.apply_async()

        return {
            "total": len(pedal_names),
            "refreshed": len(pedal_names),
            "status": "scheduled"
        }
        
    finally:
        await MongoDB.close()


# PRICE ALERT TASK (FUTURE)
@app.task(name='check_price_alerts', base=BaseTask)
def check_price_alerts_task() -> dict:
    """
    Check if any pedals dropped below user price alerts.
    
    TODO: Implement when user alerts feature is added.
    
    Returns:
        Alert stats
    """
    logger.info("Checking price alerts")
    
    # TODO: Implement
    # 1. Get all active price alerts from users collection
    # 2. Check current prices vs alert thresholds
    # 3. Send email notifications for triggered alerts
    # 4. Mark alerts as notified
    
    return {
        "checked": 0,
        "triggered": 0,
        "notifications_sent": 0
    }











