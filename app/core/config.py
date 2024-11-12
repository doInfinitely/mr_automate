import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    USERNAME = os.getenv("USERNAME", "default_user")
    PASSWORD = os.getenv("PASSWORD", "default_pass")
    MAX_PAGES = int(os.getenv("MAX_PAGES", 50))
    API_KEY = os.getenv("API_KEY", "default_api_key")
    DEBUG = bool(os.getenv("DEBUG", True))

config = Config()
