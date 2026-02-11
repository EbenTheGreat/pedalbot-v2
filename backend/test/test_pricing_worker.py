"""
Test pricing worker.

This tests the Reverb API integration for market pricing:
1. Fetch current prices from Reverb
2. Update MongoDB with pricing data
3. Check price alerts
4. Send notifications

Run: uv run python -m backend.test.test_pricing_worker
"""

from backend.workers.pricing_worker import (
    refresh_pricing_task,
    refresh_all_pricing_task,
    check_price_alerts_task
)


def test_single_pedal_pricing():
    """Test fetching price for a single pedal."""
    print("\nTesting single pedal pricing...")
    
    # Test with a popular pedal
    pedal_name = "Boss DS-1"
    
    # Call with keyword argument since task is bound (has self)
    result = refresh_pricing_task.delay(pedal_name)
    print(f"✓ Pricing task queued: {result.id}")
    print(f"   Pedal: {pedal_name}")
    
    return result.id


def test_price_alerts():
    """Test price alert checking."""
    print("\n Testing price alerts...")
    
    result = check_price_alerts_task.delay()
    print(f"✓ Price alert check queued: {result.id}")
    
    return result.id


def test_bulk_pricing_refresh():
    """Test refreshing all pedal prices."""
    print("\n Testing bulk pricing refresh...")
    print("    WARNING: This will fetch prices for ALL pedals in database")
    print("   This may take several minutes and use API quota")
    
    response = input("\nContinue? (y/n): ")
    
    if response.lower() == 'y':
        result = refresh_all_pricing_task.delay()
        print(f"✓ Bulk refresh queued: {result.id}")
        return result.id
    else:
        print("   Skipped bulk refresh")
        return None


if __name__ == "__main__":
    print("\n Testing Pricing Worker\n")
    print("=" * 50)
    
    print("\n⚠️  REQUIREMENTS:")
    print("   • REVERB_API_KEY must be set in .env")
    print("   • At least one pedal in MongoDB database")
    print("   • Reverb API quota available")
    
    response = input("\nReady to test? (y/n): ")
    
    if response.lower() != 'y':
        print("\n Test cancelled")
        exit()
    
    # Test 1: Single pedal pricing
    task1 = test_single_pedal_pricing()
    
    # Test 2: Price alerts
    task2 = test_price_alerts()
    
    # Test 3: Bulk refresh (optional)
    task3 = test_bulk_pricing_refresh()
    
    print("\n" + "=" * 50)
    print("\n Tests queued successfully!")
    
    print("\n Monitor at:")
    print("   • Flower Dashboard: http://localhost:5555")
    if task1:
        print(f"   • Single pricing: http://localhost:5555/task/{task1}")
    if task2:
        print(f"   • Price alerts: http://localhost:5555/task/{task2}")
    if task3:
        print(f"   • Bulk refresh: http://localhost:5555/task/{task3}")
    
    print("\n Expected results:")
    print("   1. Reverb API queried for pricing data")
    print("   2. MongoDB updated with latest prices")
    print("   3. Price alerts checked against user targets")
    print("   4. Email sent if price dropped below target")
    
    print("\n Check Reverb API usage:")
    print("   https://reverb.com/my/account/api\n")
