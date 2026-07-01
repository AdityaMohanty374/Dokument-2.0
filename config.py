import os
from datetime import timedelta


class Settings:
    # --- Database (Neon Postgres) ---
    # Example: postgresql://user:password@ep-xxxx.us-east-2.aws.neon.tech/dokument?sslmode=require
    DATABASE_URL: str = os.environ["DATABASE_URL"]

    # --- JWT ---
    JWT_SECRET: str = os.environ["JWT_SECRET"]
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES = timedelta(days=14)

    # --- Google OAuth ---
    GOOGLE_CLIENT_ID: str = os.environ["GOOGLE_CLIENT_ID"]
    GOOGLE_CLIENT_SECRET: str = os.environ["GOOGLE_CLIENT_SECRET"]
    # Must exactly match a redirect URI registered in Google Cloud Console.
    # e.g. https://dokument-api.onrender.com/auth/google/callback
    GOOGLE_REDIRECT_URI: str = os.environ["GOOGLE_REDIRECT_URI"]

    # Where to send the browser after login completes (your Vercel frontend)
    # e.g. https://dokument-nu.vercel.app
    FRONTEND_URL: str = os.environ["FRONTEND_URL"]

    # --- Cloudflare R2 (S3-compatible) ---
    R2_ACCOUNT_ID: str = os.environ["R2_ACCOUNT_ID"]
    R2_ACCESS_KEY_ID: str = os.environ["R2_ACCESS_KEY_ID"]
    R2_SECRET_ACCESS_KEY: str = os.environ["R2_SECRET_ACCESS_KEY"]
    R2_BUCKET_NAME: str = os.environ["R2_BUCKET_NAME"]

    @property
    def R2_ENDPOINT_URL(self) -> str:
        return f"https://{self.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"


settings = Settings()
