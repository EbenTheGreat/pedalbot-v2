"""
Test all email templates to verify they work correctly.

Run this to test all email types:
    uv run python -m backend.test.test_all_emails
"""

from backend.workers.email_worker import (
    send_welcome_email_task,
    send_manual_processed_email_task,
    send_price_alert_email_task,
    send_bulk_emails_task
)


def test_welcome_email():
    """Test welcome email template."""
    print("Testing welcome email...")
    result = send_welcome_email_task.delay(
        user_email="delivered@resend.dev",
        user_name="Test User"
    )
    print(f"✓ Welcome email queued: {result.id}")


def test_manual_processed_email():
    """Test manual processed notification."""
    print("Testing manual processed email...")
    result = send_manual_processed_email_task.delay(
        user_email="delivered@resend.dev",
        pedal_name="Boss DS-1 Distortion",
        chunk_count=127
    )
    print(f"✓ Manual processed email queued: {result.id}")


def test_price_alert_email():
    """Test price alert email."""
    print(" Testing price alert email...")
    result = send_price_alert_email_task.delay(
        user_email="delivered@resend.dev",
        pedal_name="Ibanez Tube Screamer TS9",
        current_price=89.99,
        target_price=120.00
    )
    print(f"✓ Price alert email queued: {result.id}")


def test_bulk_emails():
    """Test bulk email sending."""
    print("Testing bulk emails...")
    result = send_bulk_emails_task.delay(
        emails=["delivered@resend.dev"],
        subject="PedalBot Newsletter - January 2026",
        body="""
        <h1>Welcome to the PedalBot Newsletter!</h1>
        <p>This month's highlights:</p>
        <ul>
            <li>New pedal manuals added</li>
            <li>Price tracking improvements</li>
            <li>AI answer quality updates</li>
        </ul>
        """
    )
    print(f"✓ Bulk email queued: {result.id}")


if __name__ == "__main__":
    print("\n Testing All Email Templates\n")
    print("=" * 50)
    
    test_welcome_email()
    test_manual_processed_email()
    test_price_alert_email()
    test_bulk_emails()
    
    print("\n" + "=" * 50)
    print("\n All emails queued successfully!")
    print("\n Check results at:")
    print("   • Flower Dashboard: http://localhost:5555")
    print("   • Resend Dashboard: https://resend.com/emails")
    print("\n Tip: Emails are sent to 'delivered@resend.dev' for testing")
    print("   This is Resend's test inbox that always accepts emails.\n")
