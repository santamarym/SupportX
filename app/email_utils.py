from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

from app.config import SENDGRID_API_KEY, SENDGRID_FROM_EMAIL


def send_reset_email(to_email: str, reset_token: str) -> bool:
    """Sends a password reset email via SendGrid."""
    print(f"DEBUG: send_reset_email() was called for {to_email}")
    body = f"""Hi,

You requested a password reset for your SupportX account.

Your reset code is: {reset_token}

Enter this code on the "Reset your password" screen to set a new password.
This code expires in 30 minutes.

If you didn't request this, you can safely ignore this email.

— SupportX
"""

    message = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject="Reset your SupportX password",
        plain_text_content=body,
    )

    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        print(f"SendGrid response status: {response.status_code}")
        print(f"SendGrid response body: {response.body}")
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Failed to send reset email via SendGrid: {e}")
        return False

def send_incident_email(to_email: str, subject: str, message: str) -> bool:
    """Sends a general-purpose announcement email (e.g. incident notice)
    via SendGrid — reuses the same working setup as password reset."""
    mail = Mail(
        from_email=SENDGRID_FROM_EMAIL,
        to_emails=to_email,
        subject=subject,
        plain_text_content=message,
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(mail)
        return response.status_code in [200, 201, 202]
    except Exception as e:
        print(f"Failed to send incident email to {to_email}: {e}")
        return False