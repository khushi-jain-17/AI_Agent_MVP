import logging
from rich.logging import RichHandler
from src.config import settings

def setup_logger(name: str = "mvp_tracker") -> logging.Logger:
    """Sets up a beautiful, structured logger using Rich."""
    # Configure root logger to output to rich handler
    logging.basicConfig(
        level=settings.log_level,
        format="%(name)s - %(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True, markup=True)]
    )
    
    logger = logging.getLogger(name)
    logger.setLevel(settings.log_level)
    return logger

logger = setup_logger()
