
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY", "dev-local-xyz")
FMCSA_API_KEY = os.getenv("FMCSA_API_KEY", "")
FMCSA_BASE_URL = os.getenv("FMCSA_BASE_URL", "")
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "*")
