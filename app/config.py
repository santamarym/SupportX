import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./supportx.db")

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-this-before-deployment")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")