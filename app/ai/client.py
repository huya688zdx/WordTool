import logging
import time
from typing import Any, List, Dict, Optional

from openai import OpenAI

from app.ai import get_ai_logger, get_conv_logger, make_http_client

logger = logging.getLogger(__name__)
_ai_log = get_ai_logger()
_conv_log = get_conv_logger()


def _is_response_format_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "response_format" in msg or "json_object" in msg


class LLMClient:
    """OpenAI-compatible LLM client supporting multiple providers."""

    PROVIDER_CONFIGS = {
        "GPT-4.1": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4.1",
        },
        "GPT-4o": {
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-4o",
        },
        "DeepSeek-V3": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
        "DeepSeek-V4": {
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-v4-flash",
        },
        "Gemini-2.5": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "model": "gemini-2.5-pro-exp-03-25",
        },
    }

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=make_http_client(),
        )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, str]] = None,
    ) -> str:
        request_id = f"req-{int(time.time() * 1000)}"
        _ai_log.info(
            "[REQ %s] model=%s base_url=%s temperature=%.2f",
            request_id, self.model, self.base_url, temperature,
        )
        # Full conversation log (untruncated)
        _conv_log.info("=== REQ %s ===", request_id)
        _conv_log.info("model=%s base_url=%s temperature=%.2f", self.model, self.base_url, temperature)
        for i, msg in enumerate(messages):
            role = msg.get("role", "?")
            content = msg.get("content", "")
            if isinstance(content, str):
                preview = content[:300] + ("..." if len(content) > 300 else "")
                _conv_log.info("--- msg[%d] role=%s ---\n%s", i, role, content)
            else:
                # Vision content (list of parts) — log text parts, skip base64 blobs
                preview = str(content)[:300]
                _conv_log.info("--- msg[%d] role=%s (vision) ---\n%s", i, role, content)
            _ai_log.debug("[REQ %s] msg[%d] role=%s content=%s", request_id, i, role, preview)

        t0 = time.time()
        try:
            request_kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
            }
            if max_tokens is not None:
                request_kwargs["max_tokens"] = max_tokens
            if response_format is not None:
                request_kwargs["response_format"] = response_format

            try:
                response = self._client.chat.completions.create(**request_kwargs)
            except Exception as e:
                if response_format is None or not _is_response_format_error(e):
                    raise
                _ai_log.warning(
                    "[REQ %s] provider rejected response_format; retrying without it",
                    request_id,
                )
                request_kwargs.pop("response_format", None)
                response = self._client.chat.completions.create(**request_kwargs)
            elapsed = time.time() - t0
            content = response.choices[0].message.content or ""
            usage = response.usage
            _ai_log.info(
                "[RES %s] elapsed=%.1fs tokens_in=%d tokens_out=%d",
                request_id, elapsed,
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
            )
            _ai_log.debug("[RES %s] content=%s", request_id, content[:500])
            _conv_log.info("=== RES %s elapsed=%.1fs tokens_in=%d tokens_out=%d ===",
                           request_id, elapsed,
                           usage.prompt_tokens if usage else 0,
                           usage.completion_tokens if usage else 0)
            _conv_log.info("%s", content)
            return content
        except Exception as e:
            elapsed = time.time() - t0
            _ai_log.error("[ERR %s] elapsed=%.1fs error=%s", request_id, elapsed, str(e))
            raise

    def test_connection(self) -> bool:
        try:
            self._client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
            )
            return True
        except Exception as e:
            logger.warning(f"LLM connection test failed: {e}")
            return False


def create_client(provider: str, api_key: str) -> Optional[LLMClient]:
    """Create a client from a preset provider name."""
    config = LLMClient.PROVIDER_CONFIGS.get(provider, {})
    base_url = config.get("base_url", "https://api.openai.com/v1")
    model = config.get("model", "gpt-4o")
    return LLMClient(api_key=api_key, base_url=base_url, model=model)
