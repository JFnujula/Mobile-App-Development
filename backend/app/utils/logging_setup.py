import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Plain, single-line logs to stdout (collected by Docker/systemd). Request bodies are never logged."""
    root = logging.getLogger()
    root.handlers.clear()
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root.addHandler(h)
    root.setLevel(level.upper())
