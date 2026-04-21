import logging
from logging.handlers import RotatingFileHandler

from app.config import config

def setup_logging():
    """
    Configure console and file logging once per process.
    """
    root_logger = logging.getLogger()
    if getattr(root_logger, "_casino_logging_configured", False):
        return root_logger

    root_logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        config.storage.log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    discord_logger = logging.getLogger("discord")
    discord_logger.setLevel(logging.INFO)
    root_logger._casino_logging_configured = True  # type: ignore[attr-defined]
    return root_logger
