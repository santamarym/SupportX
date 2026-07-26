"""Knowledge Base for SupportX, themed around TechServe Solutions as a B2B
SaaS company (project/workflow management software). In production this
would live in the database and be searched via vector/semantic search —
for this demo, a categorized list works fine since we pass it all directly
to the AI as context."""

KB_ARTICLES = [
    # ---------- Account & Login ----------
    {
        "category": "Account & Login",
        "title": "Resetting your password",
        "content": "Go to the login page and click 'Forgot password?'. Enter your registered "
                    "email and you'll receive a reset code by email. Enter that code along with "
                    "your new password to complete the reset.",
    },
    {
        "category": "Account & Login",
        "title": "Enabling two-factor authentication (2FA)",
        "content": "Go to Account Settings > Security > Two-Factor Authentication and follow "
                    "the setup steps using an authenticator app. Once enabled, you'll need a "
                    "code from your app each time you log in from a new device.",
    },
    {
        "category": "Account & Login",
        "title": "Changing your email address",
        "content": "Go to Account Settings > Profile > Email. You'll need to verify the new "
                    "email address via a confirmation link before the change takes effect.",
    },
    {
        "category": "Account & Login",
        "title": "Account locked after failed login attempts",
        "content": "After 5 failed login attempts, accounts are temporarily locked for 15 "
                    "minutes as a security measure. Wait 15 minutes and try again, or use "
                    "'Forgot password?' to reset immediately.",
    },

    # ---------- Billing & Payments ----------
    {
        "category": "Billing & Payments",
        "title": "Updating billing information",
        "content": "Go to Account Settings > Billing to update your card details or billing "
                    "address. Changes apply to your next billing cycle.",
    },
    {
        "category": "Billing & Payments",
        "title": "Why was I charged twice?",
        "content": "Duplicate charges are usually a temporary authorization hold that "
                    "disappears within 3-5 business days and is not an actual double charge. "
                    "If both charges are still present after 5 business days, this needs to be "
                    "escalated to our billing team for a refund.",
    },
    {
        "category": "Billing & Payments",
        "title": "Requesting a refund",
        "content": "Refund requests can be made within 14 days of purchase from Account "
                    "Settings > Billing > Request Refund. Refunds outside this window need "
                    "manual review by our support team.",
    },
    {
        "category": "Billing & Payments",
        "title": "Downloading past invoices",
        "content": "Go to Account Settings > Billing > Invoice History to view and download "
                    "PDF copies of all past invoices.",
    },
    {
        "category": "Billing & Payments",
        "title": "Upgrading or downgrading your plan",
        "content": "Go to Account Settings > Billing > Change Plan. Upgrades take effect "
                    "immediately with prorated billing; downgrades take effect at the start of "
                    "your next billing cycle.",
    },

    # ---------- Technical Issues ----------
    {
        "category": "Technical Issues",
        "title": "App crashing on startup",
        "content": "Try these steps in order: 1) Restart your device, 2) Make sure you're on "
                    "the latest app version, 3) Clear the app cache from your device settings, "
                    "4) Reinstall the app. This resolves most startup crashes.",
    },
    {
        "category": "Technical Issues",
        "title": "Dashboard loading slowly",
        "content": "Slow dashboard loading is often caused by having too many active projects "
                    "displayed at once. Try filtering to 'My Projects' only, or clear your "
                    "browser cache if using the web app.",
    },
    {
        "category": "Technical Issues",
        "title": "File upload failing",
        "content": "File uploads are limited to 25MB per file. If your file is under this "
                    "limit and still failing, check your internet connection or try a "
                    "different browser.",
    },
    {
        "category": "Technical Issues",
        "title": "Notifications not showing up",
        "content": "Check Account Settings > Notifications to confirm email/in-app "
                    "notifications are enabled. Also check your email provider's spam folder "
                    "for missed notifications.",
    },

    # ---------- Data & Reports ----------
    {
        "category": "Data & Reports",
        "title": "Exporting reports to CSV or PDF",
        "content": "Go to any report page and click the Export button in the top-right "
                    "corner. Choose CSV for raw data or PDF for a formatted summary.",
    },
    {
        "category": "Data & Reports",
        "title": "Data showing incorrectly on dashboard",
        "content": "Dashboard data refreshes every 15 minutes. If numbers look wrong "
                    "immediately after making a change, wait for the next refresh cycle. "
                    "Persistent incorrect data needs to be escalated for investigation.",
    },

    # ---------- Integrations ----------
    {
        "category": "Integrations",
        "title": "Connecting Slack notifications",
        "content": "Go to Account Settings > Integrations > Slack and click Connect. "
                    "You'll be prompted to authorize SupportX in your Slack workspace.",
    },
    {
        "category": "Integrations",
        "title": "API access and keys",
        "content": "Go to Account Settings > Developer > API Keys to generate a new API key. "
                    "Keep your key private — it grants full account access.",
    },

    # ---------- Feature Requests ----------
    {
        "category": "Feature Requests",
        "title": "Requesting a new feature",
        "content": "We welcome feature requests! Submit them via Account Settings > Feedback, "
                    "or mention it here and I'll log it as a low-priority ticket for our "
                    "product team to review.",
    },
]


