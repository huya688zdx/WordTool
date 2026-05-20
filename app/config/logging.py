import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Suppress noisy libraries
    logging.getLogger("lxml").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
