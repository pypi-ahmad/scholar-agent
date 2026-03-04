import logging
import sys

def setup_logger(name: str = "research_agent") -> logging.Logger:
    """Configure and return a customized logger."""
    logger = logging.getLogger(name)
    
    # Only configure if no handlers exist
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # Create console handler with formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # Create formatter and add it to the handler
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        
    return logger

logger = setup_logger()
