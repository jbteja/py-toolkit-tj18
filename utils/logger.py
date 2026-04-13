import logging
import os
import sys


class CustomFormatter(logging.Formatter):
    """
    Standard Library Formatter that adds colors based on log levels.
    """

    # ANSI Color Codes
    grey = "\x1b[38;20m"
    blue = "\x1b[34;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"

    # The format string (similar to your previous Loguru format)
    format_str = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d - %(message)s"
    )

    FORMATS = {
        logging.DEBUG: grey + format_str + reset,
        logging.INFO: blue + format_str + reset,
        logging.WARNING: yellow + format_str + reset,
        logging.ERROR: red + format_str + reset,
        logging.CRITICAL: bold_red + format_str + reset,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%m:%S")
        return formatter.format(record)


def get_logger(name="app_logger"):
    """
    Sets up a logger with the custom color formatter.
    """
    # Get the log level from environment or default to INFO
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Check if the logger already has handlers to prevent duplicate logs
    if not logger.handlers:
        # Create console handler and set level
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(level)

        # Add custom formatter to ch
        ch.setFormatter(CustomFormatter())

        # Add ch to logger
        logger.addHandler(ch)

    return logger


# Pre-initialize a default logger for easy importing
logger = get_logger("Utils")

# --- Local Testing Block ---
if __name__ == "__main__":
    # Test different levels
    test_logger = get_logger("TestLogger")

    test_logger.debug("This is a debug message (usually hidden)")
    test_logger.info("This is an info message")
    test_logger.warning("This is a warning message")
    test_logger.error("This is an error message")
    test_logger.critical("This is a critical message")

    # Example of logging an exception
    try:
        1 / 0
    except ZeroDivisionError:
        test_logger.exception("Caught an exception with a traceback!")
