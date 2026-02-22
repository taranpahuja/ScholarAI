import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY")         # anon/public key
    SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # service role key (admin ops)
    MEGALLLM_API_KEY = os.getenv("MEGALLLM_API_KEY")
    MEGALLLM_API_URL = os.getenv("MEGALLLM_API_URL", "https://api.megalllm.com/v1/chat/completions")
    MEGALLLM_MODEL = os.getenv("MEGALLLM_MODEL", "mega-llm-latest")
