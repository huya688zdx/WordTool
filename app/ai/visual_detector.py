"""AI visual heading level verification using vision models.

Sends page screenshots to a vision-capable LLM to verify whether
Word COM's heading levels are correct. Does NOT detect coordinates —
Word COM positions are always used for that.
"""

from __future__ import annotations

import base64
import json
import re
import time

from app.ai import get_ai_logger, get_conv_logger
from app.ai.prompt_layout import SYSTEM_PROMPT_VISUAL_HEADING, make_visual_heading_prompt

_ai_logger = get_ai_logger()
_conv_logger = get_conv_logger()


class VisualPageDetector:
    """Verify heading levels on a page using a vision model."""

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

    def verify_headings(
        self,
        page_image_bytes: bytes,
        page_number: int,
        total_pages: int,
        paragraphs: list[dict],
    ) -> list[dict]:
        """Verify heading levels for paragraphs on a page image.

        Args:
            page_image_bytes: PNG image of the page
            page_number: 1-based page number
            total_pages: Total page count
            paragraphs: Paragraphs on this page.
                Each dict: index, text, heading_level

        Returns:
            List of heading corrections: [{"index": 5, "heading_level": 1, "reason": "..."}]
        """
        image_b64 = base64.b64encode(page_image_bytes).decode("ascii")
        data_uri = f"data:image/png;base64,{image_b64}"
        user_prompt = make_visual_heading_prompt(
            page_number, total_pages, paragraphs,
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT_VISUAL_HEADING},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            },
        ]

        request_id = f"visual-heading-p{page_number}-{int(time.time() * 1000)}"
        _ai_logger.info(
            "[REQ %s] model=%s base_url=%s page=%d/%d paras=%d image=%d bytes",
            request_id, self.model, self.base_url, page_number, total_pages,
            len(paragraphs), len(page_image_bytes),
        )

        # Full conversation log
        _conv_logger.info("=== REQ %s ===", request_id)
        _conv_logger.info("model=%s base_url=%s page=%d/%d paras=%d image=%d bytes",
                          self.model, self.base_url, page_number, total_pages,
                          len(paragraphs), len(page_image_bytes))
        _conv_logger.info("--- system ---\n%s", SYSTEM_PROMPT_VISUAL_HEADING)
        _conv_logger.info("--- user (text) ---\n%s", user_prompt)
        _conv_logger.info("--- user (image) --- [%d bytes base64 PNG]", len(image_b64))

        t0 = time.time()
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.1,
                max_tokens=16384,
            )
            elapsed = time.time() - t0
            content = response.choices[0].message.content or ""
            finish_reason = response.choices[0].finish_reason or ""
            usage = response.usage
            _ai_logger.info(
                "[RES %s] elapsed=%.1fs tokens_in=%d tokens_out=%d finish=%s",
                request_id, elapsed,
                usage.prompt_tokens if usage else 0,
                usage.completion_tokens if usage else 0,
                finish_reason,
            )

            _conv_logger.info("=== RES %s elapsed=%.1fs tokens_in=%d tokens_out=%d finish=%s ===",
                              request_id, elapsed,
                              usage.prompt_tokens if usage else 0,
                              usage.completion_tokens if usage else 0,
                              finish_reason)
            _conv_logger.info("%s", content)

            if finish_reason == "length":
                _ai_logger.warning("[RES %s] output TRUNCATED by token limit! Trying to salvage...",
                                   request_id)

            corrections = self._parse_corrections(content)
            _ai_logger.info("[RES %s] %d heading corrections", request_id, len(corrections))
            for c in corrections:
                _ai_logger.info("  [%d] → H%d: %s",
                                c.get("index"), c.get("heading_level"), c.get("reason", ""))
            return corrections

        except Exception as e:
            elapsed = time.time() - t0
            _ai_logger.error("[ERR %s] elapsed=%.1fs error=%s", request_id, elapsed, str(e))
            return []

    @staticmethod
    def _parse_corrections(content: str) -> list[dict]:
        """Extract heading corrections from AI response JSON.

        Handles truncated JSON by trying to repair missing brackets.
        """
        json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                json_str = content[brace_start:brace_end + 1]
            else:
                json_str = content

        if not json_str:
            _ai_logger.warning("Empty JSON in visual heading response")
            return []

        # Try parsing, with progressive repair for truncated JSON
        try:
            data = json.loads(json_str)
            return data.get("corrections", [])
        except json.JSONDecodeError as e:
            _ai_logger.warning("JSON parse failed (will try repair): %s", str(e))

        # Attempt repair: close unclosed brackets/braces
        for repair in _repair_attempts(json_str):
            try:
                data = json.loads(repair)
                corrections = data.get("corrections", [])
                if corrections:
                    _ai_logger.info("JSON repaired: salvaged %d corrections", len(corrections))
                return corrections
            except json.JSONDecodeError:
                continue

        _ai_logger.warning("All JSON repair attempts failed. Raw: %s", content[:500])
        return []


def _repair_attempts(json_str: str):
    """Generate repair attempts for truncated JSON by closing open brackets."""
    # Count open vs close
    open_braces = json_str.count("{") - json_str.count("}")
    open_brackets = json_str.count("[") - json_str.count("]")
    # Check if inside a string (unclosed quote)
    in_string = json_str.count('"') % 2 == 1
    base = json_str

    if in_string:
        yield base + '"}'
        yield base + ']"}'
        yield base + '"}]}'
        yield base.rstrip('"') + '}]}'

    # Close brackets then braces
    suffix = "]" * open_brackets + "}" * open_braces
    if suffix:
        yield base + suffix
    # Also try trimming to last valid item then closing
    last_comma = base.rfind(",")
    if last_comma > 0 and open_braces > 0:
        yield base[:last_comma] + "}]}"
