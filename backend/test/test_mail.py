from backend.workers.email_worker import send_welcome_email_task


# send_welcome_email_task.delay( # type: ignore[attr-defined]
#     user_email="ezebina360@gmail.com",
#     user_name="Test User"
# )

if __name__ == "__main__":
    # Use Resend's test email - works without domain verification
    # Emails sent here will show as delivered in Resend dashboard
    send_welcome_email_task.delay( # type: ignore[attr-defined]
        user_email="ezebina360@gmail.com",
        user_name="Test User"
    )
