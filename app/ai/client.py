import logging
from typing import List, Dict, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)


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
        "Gemini-2.5": {
            "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
            "model": "gemini-2.5-pro-exp-03-25",
        },
    }

    def __init__(self, api_key: str, base_url: str = "", model: str = ""):
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def chat(self, messages: List[Dict[str, str]], temperature: float = 0.3) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
        )
        return response.choices[0].message.content

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
