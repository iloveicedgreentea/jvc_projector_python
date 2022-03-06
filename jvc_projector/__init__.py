import logging
import os

log_level = os.getenv("LOG_LEVEL", "info")
level = logging.getLevelName(log_level.upper())

logging.basicConfig(level=level)
