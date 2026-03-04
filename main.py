import os
from dotenv import load_dotenv

# C-01: load_dotenv must execute before any application module is imported
# so that os.getenv() calls inside those modules see the correct values.
load_dotenv()

import uvicorn
from app.utils.logger import logger

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    reload_enabled = os.getenv("RELOAD", "true").lower() == "true"
    
    logger.info(f"Starting Multi-Agent Research API on {host}:{port}")
    uvicorn.run("api.app:app", host=host, port=port, reload=reload_enabled)
