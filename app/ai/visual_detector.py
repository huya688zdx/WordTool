"""AI-assisted visual paragraph detection using vision models.

Sends page screenshots to a vision-capable LLM (GPT-4o, Gemini, etc.)
to detect paragraph boundaries visually. This handles CJK documents
where text search fails due to garbled PDF text extraction.
"""

from __future__ import annotations

import base64
import json
import re
import time
from typing import Optional

from app.ai import get_ai_logger, get_conv_logger
from app.ai.prompt_layout import SYSTEM_PROMPT_LAYOUT, make_layout_prompt

_ai_logger = get_ai_logger()
_conv_logger = get_conv_logger()


class VisualPageDetector:
    """Detect paragraph regions on a page using a vision model."""

    def __init__(self, api_key: str, base_url: str, model: str):
        from openai import OpenAI
        from app.ai import make_http_client
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self._client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=make_http_client(),
        )

    def detect(
        self,
        page_image_bytes: bytes,
        page_number: int = 1,
        total_pages: int = 1,
        doc_hint: str = "",
        existing_paragraphs: list[dict] | None = None,
    ) -> list[dict]:
        """Verify and correct paragraph positions on a page image.

        Args:
            page_image_bytes: PNG image of the page
            page_number: 1-based page number
            total_pages: Total page count
            doc_hint: Optional document description
            existing_paragraphs: Pre-detected paragraphs from Word COM.
                Each dict: index, text, x0_pct, y0_pct, x1_pct, y1_pct, heading_level

        Returns:
            List of dicts with keys: index, type, x0, y0, x1, y1, content_preview
        """
        image_b64 = base64.b64encode(page_image_bytes).decode("ascii")
        data_uri = f"data:image/png;base64,{image_b64}"
        user_prompt = make_layout_prompt(
            page_number, total_pages, doc_hint,
            existing_paragraphs=existing_paragraphs,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_LAYOUT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ]

        request_id = f"layout-p{page_number}-{int(time.time() * 1000)}"
        _ai_logger.info(
            "[REQ %s] model=%s base_url=%s page=%d/%d image_size=%d bytes",
            request_id, self.model, self.base_url, page_number, total_pages,
            len(page_image_bytes),
        )
        _ai_logger.debug(
            "[REQ %s] system_prompt=%s", request_id,
            SYSTEM_PROMPT_LAYOUT[:200] + "...",
        )
        _ai_logger.debug(
            "[REQ %s] user_prompt=%s", request_id, user_prompt,
        )

        # Full conversation log (image replaced with size placeholder)
        _conv_logger.info("=== REQ %s ===", request_id)
        _conv_logger.info("model=%s base_url=%s page=%d/%d image_size=%d",
                          self.model, self.base_url, page_number, total_pages,
                          len(page_image_bytes))
        _conv_logger.debug("--- system ---\n%s", SYSTEM_PROMPT_LAYOUT)
        _conv_logger.debug("--- user (text) ---\n%s", user_prompt)
        _conv_logger.debug("--- user (image) --- [%d bytes base64 PNG]", len(image_b64))

        t0 = time.time()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,  # low temperature for precise coordinates
                max_tokens=16384,
            )
            elapsed = time.time() - t0
            content = response.choices[0].message.content or ""
            usage = response.usage
            _ai_logger.info(
                "[RES %s] elapsed=%.1fs tokens_in=%d tokens_out=%d",
                request_id, elapsed,
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
            )
            _ai_logger.debug("[RES %s] raw_content=%s", request_id, content)

            _conv_logger.info("=== RES %s elapsed=%.1fs tokens_in=%d tokens_out=%d ===",
                              request_id, elapsed,
                              usage.prompt_tokens if usage else 0,
                              usage.completion_tokens if usage else 0)
            _conv_logger.debug("%s", content)

            paragraphs = self._parse_response(content)
            _ai_logger.info(
                "[RES %s] parsed=%d paragraphs",
                request_id, len(paragraphs),
            )
            for p in paragraphs:
                _ai_logger.debug(
                    "[RES %s]   para[%d] type=%s bbox=(%.0f,%.0f,%.0f,%.0f) preview=%s",
                    request_id, p.get("index"), p.get("type"),
                    p.get("x0", 0), p.get("y0", 0),
                    p.get("x1", 0), p.get("y1", 0),
                    p.get("content_preview", "")[:50],
                )
            return paragraphs

        except Exception as e:
            elapsed = time.time() - t0
            _ai_logger.error(
                "[ERR %s] elapsed=%.1fs error=%s",
                request_id, elapsed, str(e),
            )
            raise

    @staticmethod
    def _parse_response(content: str) -> list[dict]:
        """Extract JSON from the AI response, handling markdown code fences."""
        # Try to find JSON block within markdown code fences
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Try to extract the first {...} object
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                json_str = content[brace_start:brace_end + 1]
            else:
                json_str = content

        try:
            data = json.loads(json_str)
            if "paragraphs" in data:
                return data["paragraphs"]
            return []
        except json.JSONDecodeError:
            _ai_logger.warning("Failed to parse AI response as JSON: %s", content[:500])
            return []


def detect_page_layout(
    api_key: str,
    base_url: str,
    model: str,
    page_image_bytes: bytes,
    page_number: int = 1,
    total_pages: int = 1,
    doc_hint: str = "",
) -> list[dict]:
    """Convenience function for page layout detection."""
    detector = VisualPageDetector(api_key, base_url, model)
    return detector.detect(page_image_bytes, page_number, total_pages, doc_hint)
