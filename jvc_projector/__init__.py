from .jvc_projector import JVCProjector
import logging
import sys
import os

log_level = os.getenv("LOG_LEVEL", "info")
level = logging.getLevelName(log_level.upper())

logging.basicConfig(stream=sys.stdout, level=level)
