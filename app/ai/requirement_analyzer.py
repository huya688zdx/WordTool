import json
from typing import Optional

from app.ai import get_ai_logger
from app.ai.client import LLMClient
from app.ai.prompt_templates import SYSTEM_PROMPT, make_analysis_prompt

_log = get_ai_logger()


class RequirementAnalyzer:
    """Analyze requirement changes using LLM."""

    def __init__(self, client: LLMClient):
        self.client = client

    def analyze(
        self,
        paragraph_text: str,
        code_context: str = "",
    ) -> str:
        _log.info("Analyzing requirement paragraph (%d chars)", len(paragraph_text))

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": make_analysis_prompt(paragraph_text, code_context)},
        ]

        try:
            response = self.client.chat(
                messages,
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            _log.info("Analysis completed (%d chars)", len(response))
            return response
        except Exception as e:
            _log.error("Analysis failed: %s", e)
            return f"分析失败: {e}"


def analyze_requirement(
    api_key: str,
    base_url: str,
    model: str,
    paragraph_text: str,
    code_context: str = "",
) -> str:
    """Convenience function for requirement analysis."""
    client = LLMClient(api_key=api_key, base_url=base_url, model=model)
    analyzer = RequirementAnalyzer(client)
    return analyzer.analyze(paragraph_text, code_context)
