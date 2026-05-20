import logging
import sys
import os


def _detect_encoding() -> str:
    """Detect the best encoding for console output on CJK Windows systems."""
    if sys.platform != "win32":
        return "utf-8"

    # Try common CJK encodings
    for enc in ["utf-8", "cp932", "shift_jis", "cp936", "gbk"]:
        try:
            "test".encode(enc)
            return enc
        except (LookupError, UnicodeError):
            continue
    return "utf-8"


class EncodingStreamHandler(logging.StreamHandler):
    """StreamHandler that re-encodes output for CJK console compatibility."""

    def __init__(self, stream=None):
        super().__init__(stream)
        self._encoding = _detect_encoding()

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Write with proper encoding for CJK consoles
            if hasattr(stream, "buffer"):
                try:
                    stream.buffer.write(msg.encode(self._encoding, errors="replace") + b"\n")
                    stream.flush()
                    return
                except Exception:
                    pass
            stream.write(msg + "\n")
            stream.flush()
        except Exception:
            self.handleError(record)


def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging with CJK encoding support."""
    log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    encoding = _detect_encoding()

    # Reconfigure stdout/stderr for CJK
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding=encoding, errors="replace")
            except Exception:
                pass

    # Set PYTHONIOENCODING for subprocesses
    if encoding != "utf-8":
        os.environ.setdefault("PYTHONIOENCODING", encoding)

    handler = EncodingStreamHandler(sys.stdout)

    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=log_format,
        handlers=[handler],
        force=True,
    )

    # Suppress noisy libraries
    logging.getLogger("lxml").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
