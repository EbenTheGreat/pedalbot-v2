"""
Test email sending without Celery/Redis (synchronous execution).
This is useful for testing email functionality without running Redis.
"""
from backend.workers.email_worker import send_email_task

if __name__ == "__main__":
    # Call the task function directly (not as a Celery task)
    result = send_email_task(
        to_email="ezebina360@gmail.com",
        subject="Welcome to PedalBot",
        body="""
Hi! Ebenezer,

Welcome to PedalBot!
We're excited to help you explore the world of guitar pedals with:
• Instant answers from pedal manuals
• Real-time market pricing
• Expert tone advice

Get started by asking questions like:
• "What's the input impedance of the Boss DS-1?"
• "How much does an Ibanez TS9 cost?"
• "Where should I put my delay in my signal chain?"

Happy playing!

The PedalBot Team
        """
    )
    
    print(f"Email send result: {result}")
