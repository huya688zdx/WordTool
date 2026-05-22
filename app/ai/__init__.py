"""AI module — shared logger, httpx compat, and proxy bypass for all AI requests."""

import logging
import os
from pathlib import Path

import httpx

# ── httpx compatibility patch (must run before any OpenAI import) ──────────
# Newer openai (>=1.40) passes `proxies` (plural) to httpx.Client, but older
# httpx (<=0.28) only accepts `proxy` (singular).
_orig_init = httpx.Client.__init__


def _patched_init(self, *args, **kwargs):
    if "proxies" in kwargs and "proxy" not in kwargs:
        kwargs["proxy"] = kwargs.pop("proxies")
    _orig_init(self, *args, **kwargs)


httpx.Client.__init__ = _patched_init


# ── Shared proxy-free HTTP client factory ──────────────────────────────────
def make_http_client() -> httpx.Client:
    """Create an httpx.Client that does NOT use system proxy env vars."""
    env_proxies = {k: v for k, v in os.environ.items()
                   if k.upper() in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY")}
    for k in env_proxies:
        os.environ.pop(k, None)
    try:
        return httpx.Client(proxy=None, trust_env=False)
    finally:
        os.environ.update(env_proxies)


# ── Shared AI audit logger ─────────────────────────────────────────────────
_ai_logger = logging.getLogger("wordagent.ai")
_ai_logger.setLevel(logging.DEBUG)

if not _ai_logger.handlers:
    _log_dir = Path("./data/logs")
    _log_dir.mkdir(parents=True, exist_ok=True)

    _fh = logging.FileHandler(_log_dir / "ai_requests.log", encoding="utf-8")
    _fh.setLevel(logging.DEBUG)
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _ai_logger.addHandler(_fh)

    _sh = logging.StreamHandler()
    _sh.setLevel(logging.DEBUG)
    _sh.setFormatter(logging.Formatter("%(levelname)s | %(message)s"))
    _ai_logger.addHandler(_sh)

    _ai_logger.propagate = False


def get_ai_logger() -> logging.Logger:
    return _ai_logger


# ── Full conversation logger (no truncation, file-only) ─────────────────────
_conv_logger = logging.getLogger("wordagent.ai.conversation")
_conv_logger.setLevel(logging.DEBUG)

if not _conv_logger.handlers:
    _conv_dir = Path("./data/logs")
    _conv_dir.mkdir(parents=True, exist_ok=True)

    _cfh = logging.FileHandler(_conv_dir / "ai_conversations.log", encoding="utf-8")
    _cfh.setLevel(logging.DEBUG)
    _cfh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _conv_logger.addHandler(_cfh)
    _conv_logger.propagate = False


def get_conv_logger() -> logging.Logger:
    """Logger that writes FULL AI prompts/responses to ai_conversations.log."""
    return _conv_logger
