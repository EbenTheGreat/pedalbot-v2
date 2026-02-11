"""
Email worker for notifications using Resend.

Resend is a modern email API with great deliverability.
Website: https://resend.com
"""

from celery import Task
import logging
from typing import Dict, Any

from backend.workers.celery_app import app, BaseTask

logger = logging.getLogger(__name__)


# SEND EMAIL TASK
@app.task(name='send_email', base=BaseTask, bind=True)
def send_email_task(
    self: Task,
    to_email: str,
    subject: str,
    body: str,
) -> dict:
    """
    Send email via Resend.
    
    Args:
        to_email: Recipient email
        subject: Email subject
        body: Email body (HTML)
    
    Returns:
        Send status
    """
    logger.info(f"Sending email to {to_email}: {subject}")
    
    try:
        from app.config import settings
        
        if not settings.RESEND_API_KEY:
            logger.warning("Resend not configured - email not sent")
            return {"status": "skipped", "reason": "no_api_key"}
        
        import resend
        
        # Configure Resend
        resend.api_key = settings.RESEND_API_KEY
        
        # Send email
        response = resend.Emails.send({
            "from": f"PedalBot <{settings.RESEND_FROM_EMAIL}>",
            "to": [to_email],
            "subject": subject,
            "html": body
        })
        
        logger.info(f"Email sent: {response['id']}")
        
        return {
            "status": "sent",
            "to": to_email,
            "subject": subject,
            "message_id": response['id']
        }
        
    except Exception as e:
        logger.error(f"Email failed: {e}")
        raise self.retry(exc=e, countdown=60)


# NOTIFICATION TEMPLATES
@app.task(name='send_welcome_email', base=BaseTask)
def send_welcome_email_task(user_email: str, user_name: str) -> dict:
    """
    Send welcome email to new user.
    
    Args:
        user_email: User email
        user_name: User name
    
    Returns:
        Send status
    """
    subject = "Welcome to PedalBot! 🎸"
    
    body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                   color: white; padding: 30px; text-align: center; border-radius: 10px; }}
        .content {{ padding: 30px; background: #f9f9f9; border-radius: 10px; margin-top: 20px; }}
        .feature {{ margin: 15px 0; padding: 15px; background: white; border-radius: 5px; }}
        .cta {{ text-align: center; margin: 30px 0; }}
        .button {{ background: #667eea; color: white; padding: 12px 30px; 
                   text-decoration: none; border-radius: 5px; display: inline-block; }}
        .footer {{ text-align: center; margin-top: 30px; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎸 Welcome to PedalBot!</h1>
            <p>Your AI-powered guitar pedal assistant</p>
        </div>
        
        <div class="content">
            <p>Hi {user_name},</p>
            
            <p>Thanks for joining PedalBot! We're excited to help you explore the world of guitar pedals with instant AI-powered answers.</p>
            
            <div class="feature">
                <strong>📚 Instant Manual Answers</strong>
                <p>Ask questions about any pedal and get answers from the actual manuals</p>
            </div>
            
            <div class="feature">
                <strong>💰 Real-Time Pricing</strong>
                <p>Check current market prices from Reverb to find the best deals</p>
            </div>
            
            <div class="feature">
                <strong>🎵 Expert Tone Advice</strong>
                <p>Get recommendations for your signal chain and tone</p>
            </div>
            
            <div class="cta">
                <a href="https://app.pedalbot.ai" class="button">Start Asking Questions →</a>
            </div>
            
            <p><strong>Try asking:</strong></p>
            <ul>
                <li>"What's the input impedance of the Boss DS-1?"</li>
                <li>"How much does an Ibanez TS9 cost?"</li>
                <li>"Where should I put my delay in my signal chain?"</li>
            </ul>
            
            <p>Happy playing! 🎸</p>
            <p>The PedalBot Team</p>
        </div>
        
        <div class="footer">
            <p>PedalBot - AI-Native Guitar Gear Intelligence</p>
            <p>Questions? Reply to this email or visit our <a href="https://pedalbot.ai/help">help center</a></p>
        </div>
    </div>
</body>
</html>
    """
    
    return send_email_task.delay(# type: ignore[attr-defined]
        to_email=user_email,
        subject=subject,
        body=body
    )


@app.task(name='send_manual_processed_email', base=BaseTask)
def send_manual_processed_email_task(
    user_email: str,
    pedal_name: str,
    chunk_count: int
) -> dict:
    """
    Notify user when their uploaded manual is processed.
    
    Args:
        user_email: User email
        pedal_name: Pedal name
        chunk_count: Number of chunks processed
    
    Returns:
        Send status
    """
    subject = f"Your {pedal_name} manual is ready!"
    
    body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #10b981; color: white; padding: 30px; 
                   text-align: center; border-radius: 10px; }}
        .content {{ padding: 30px; background: #f9f9f9; border-radius: 10px; margin-top: 20px; }}
        .stats {{ background: white; padding: 20px; border-radius: 5px; margin: 20px 0; }}
        .stat {{ display: inline-block; margin: 10px 20px; text-align: center; }}
        .stat-value {{ font-size: 36px; font-weight: bold; color: #667eea; }}
        .stat-label {{ color: #666; font-size: 14px; }}
        .cta {{ text-align: center; margin: 30px 0; }}
        .button {{ background: #667eea; color: white; padding: 12px 30px; 
                   text-decoration: none; border-radius: 5px; display: inline-block; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Manual Processing Complete!</h1>
            <p>{pedal_name}</p>
        </div>
        
        <div class="content">
            <p>Great news! Your <strong>{pedal_name}</strong> manual has been processed and is now fully searchable.</p>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{chunk_count}</div>
                    <div class="stat-label">Text Chunks</div>
                </div>
                <div class="stat">
                    <div class="stat-value">✓</div>
                    <div class="stat-label">Indexed</div>
                </div>
                <div class="stat">
                    <div class="stat-value">∞</div>
                    <div class="stat-label">Queries Ready</div>
                </div>
            </div>
            
            <p><strong>Try asking:</strong></p>
            <ul>
                <li>"What are the {pedal_name} specifications?"</li>
                <li>"How do I adjust the tone controls?"</li>
                <li>"What's the power consumption?"</li>
                <li>"Does it have true bypass?"</li>
            </ul>
            
            <div class="cta">
                <a href="https://app.pedalbot.ai?pedal={pedal_name}" class="button">
                    Ask Questions Now →
                </a>
            </div>
            
            <p>Your manual is now part of our growing database of guitar pedal knowledge!</p>
            
            <p>Best,<br>The PedalBot Team</p>
        </div>
    </div>
</body>
</html>
    """
    
    return send_email_task.delay(# type: ignore[attr-defined]
        to_email=user_email,
        subject=subject,
        body=body
    )


@app.task(name='send_price_alert_email', base=BaseTask)
def send_price_alert_email_task(
    user_email: str,
    pedal_name: str,
    current_price: float,
    target_price: float
) -> dict:
    """
    Send price alert when pedal drops below threshold.
    
    Args:
        user_email: User email
        pedal_name: Pedal name
        current_price: Current market price
        target_price: User's target price
    
    Returns:
        Send status
    """
    savings = target_price - current_price
    subject = f"Price Alert: {pedal_name} is now ${current_price:.2f}!"
    
    body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: linear-gradient(135deg, #f59e0b 0%, #ef4444 100%); 
                   color: white; padding: 30px; text-align: center; border-radius: 10px; }}
        .content {{ padding: 30px; background: #f9f9f9; border-radius: 10px; margin-top: 20px; }}
        .price-box {{ background: white; padding: 30px; border-radius: 10px; 
                      text-align: center; margin: 20px 0; border: 3px solid #10b981; }}
        .price {{ font-size: 48px; font-weight: bold; color: #10b981; }}
        .savings {{ color: #059669; font-size: 24px; margin-top: 10px; }}
        .comparison {{ display: flex; justify-content: space-around; 
                       margin: 20px 0; text-align: center; }}
        .comparison-item {{ flex: 1; }}
        .cta {{ text-align: center; margin: 30px 0; }}
        .button {{ background: #10b981; color: white; padding: 15px 40px; 
                   text-decoration: none; border-radius: 5px; display: inline-block; 
                   font-weight: bold; font-size: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Price Alert!</h1>
            <p>{pedal_name}</p>
        </div>
        
        <div class="content">
            <p>Great news! The <strong>{pedal_name}</strong> you've been watching has dropped in price!</p>
            
            <div class="price-box">
                <div class="price">${current_price:.2f}</div>
                <div class="savings">You save ${savings:.2f}!</div>
            </div>
            
            <div class="comparison">
                <div class="comparison-item">
                    <div style="font-size: 24px; color: #667eea;">${target_price:.2f}</div>
                    <div style="color: #666;">Your Target</div>
                </div>
                <div class="comparison-item">
                    <div style="font-size: 36px; color: #10b981;">→</div>
                </div>
                <div class="comparison-item">
                    <div style="font-size: 24px; color: #10b981;">${current_price:.2f}</div>
                    <div style="color: #666;">Current Price</div>
                </div>
            </div>
            
            <div class="cta">
                <a href="https://reverb.com/marketplace?query={pedal_name.replace(' ', '+')}" 
                   class="button">
                    View Listings on Reverb →
                </a>
            </div>
            
            <p><strong>⏰ Act fast!</strong> Prices can change quickly. This alert will expire in 24 hours to avoid spam.</p>
            
            <p>Happy shopping! 🎸</p>
            <p>The PedalBot Team</p>
        </div>
    </div>
</body>
</html>
    """
    
    return send_email_task(
        to_email=user_email,
        subject=subject,
        body=body
    )

# BULK EMAIL TASKS
@app.task(name='send_bulk_emails', base=BaseTask)
def send_bulk_emails_task(
    emails: list[str],
    subject: str,
    body: str
) -> dict:
    """
    Send bulk emails (for newsletters, announcements).
    
    Args:
        emails: List of recipient emails
        subject: Email subject
        body: Email body (HTML)
    
    Returns:
        Bulk send stats
    """
    from celery import group
    
    logger.info(f"Sending bulk email to {len(emails)} recipients")
    
    # Create parallel tasks (batched to avoid rate limits)
    batch_size = 10
    batches = [emails[i:i + batch_size] for i in range(0, len(emails), batch_size)]
    
    sent = 0
    failed = 0
    
    for batch in batches:
        job = group(
            send_email_task.s(email, subject, body)
            for email in batch
        )
        
        results = job.apply_async().get(timeout=300)
        
        sent += sum(1 for r in results if r.get("status") == "sent")
        failed += len(results) - sent
    
    logger.info(f"Bulk email complete: {sent} sent, {failed} failed")
    
    return {
        "total": len(emails),
        "sent": sent,
        "failed": failed
    }