import logging
import sys
import time
from logging.handlers import TimedRotatingFileHandler

from config import LOG_FILE, LOG_PATH


def setup_logging():
    LOG_PATH.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    formatter.converter = time.gmtime

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    file_handler = TimedRotatingFileHandler(
        LOG_PATH / LOG_FILE,
        when="midnight",
        interval=1,
        backupCount=30,
        encoding="utf-8",
        utc=True,
    )
    file_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[console_handler, file_handler],
        force=True,
    )

    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
