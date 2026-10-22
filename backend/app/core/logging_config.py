import logging
import sys

def setup_logging():
    logger = logging.getLogger("queueflow")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


logger = setup_logging()
