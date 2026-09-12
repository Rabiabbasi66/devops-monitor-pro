import os

from dotenv import load_dotenv

load_dotenv()

# Frontend API base URL.
#   - Streamlit Community Cloud sets API_URL via Secrets/app settings, but the
#     fallback default is the production backend so the public deployment works
#     out of the box.
#   - Local development overrides it via frontend/.env (API_URL=http://localhost:8000/api).
API_URL = os.getenv("API_URL", "https://devops-monitor-pro.vercel.app/api")
