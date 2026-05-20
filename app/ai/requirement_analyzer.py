import json
import logging
from typing import Optional

from app.ai.client import LLMClient
from app.ai.prompt_templates import SYSTEM_PROMPT, make_analysis_prompt

logger = logging.getLogger(__name__)


class RequirementAnalyzer:
    """Analyze requirement changes using LLM."""

    def __init__(self, client: LLMClient):
        self.client = client

    def analyze(
        self,
        paragraph_text: str,
        code_context: str = "",
    ) -> str:
        """Analyze a requirement paragraph and return structured analysis.

        Args:
            paragraph_text: The requirement text from the document
            code_context: Optional code context for impact analysis

        Returns:
            Analysis result as markdown text
        """
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": make_analysis_prompt(paragraph_text, code_context)},
        ]

        try:
            response = self.client.chat(messages)
            return response
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
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
