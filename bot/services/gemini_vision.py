"""
Сервис распознавания еды через Google Gemini Vision (бесплатный тариф).
"""

from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError, field_validator

from bot.config import get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Ты — внимательный и точный нутрициолог-ассистент. "
    "Твоя задача — максимально реалистично оценить состав и калорийность еды на фотографии.\n"
    "Всегда отвечай строго в JSON-формате без какого-либо текста вокруг.\n"
    "Если на фото несколько блюд/продуктов — разбирай каждый отдельно.\n"
    "Оценивай вес очень осторожно и реалистично (лучше немного занизить, чем завысить).\n"
    "Используй средние значения КБЖУ для обычных продуктов.\n"
    "\n"
    "Скрытые калории — очень важно:\n"
    "- Если блюдо выглядит жареным, тушёным на масле, с корочкой или блестит от жира — "
    "добавь отдельным item растительное масло / сливочное масло / жир с реалистичной порцией "
    "(обычно 5–15 г на порцию, не завышай).\n"
    "- Если видно соус, майонез, сметану, заправку, кетчуп, сыр сверху — учитывай отдельным item.\n"
    "- Если еда варёная, на пару, запечённая без блеска жира — масло НЕ добавляй.\n"
    "- Не выдумывай масло «на всякий случай», только если по виду блюда оно реально вероятно.\n"
    "\n"
    "confidence: ставь low ТОЛЬКО если продукт плохо виден, размыт, "
    "непонятен состав или вес совсем неочевиден. "
    "Для обычных чётких блюд — high или medium. Не занижай confidence без причины.\n"
    "Если что-то плохо видно — честно пиши в комментарии.\n"
    "Если на фото нет еды — верни пустой список items и comment "
    "«Кажется, это не еда»."
)

USER_PROMPT = (
    "Проанализируй это фото еды.\n"
    "Верни JSON строго следующего вида:\n\n"
    "{\n"
    '  "items": [\n'
    "    {\n"
    '      "name": "название продукта/блюда",\n'
    '      "weight_grams": число,\n'
    '      "calories": число,\n'
    '      "protein": число,\n'
    '      "fat": число,\n'
    '      "carbs": число,\n'
    '      "confidence": "high/medium/low"\n'
    "    }\n"
    "  ],\n"
    '  "total": {\n'
    '    "calories": число,\n'
    '    "protein": число,\n'
    '    "fat": число,\n'
    '    "carbs": число\n'
    "  },\n"
    '  "comment": "короткий дружелюбный комментарий на русском (1 предложение)"\n'
    "}\n\n"
    "Важно:\n"
    "- weight_grams — реалистичная оценка\n"
    "- Все числа — целые\n"
    "- Жареное / с маслом / с соусом: вынеси масло, соус, майонез отдельными items, "
    "если они реально участвуют в блюде (например: «Картофель жареный», «Масло растительное»)\n"
    "- Готовое сложное блюдо (плов, рагу) можно одним item, но калории должны включать "
    "типичное масло и заправку\n"
    "- Не выдумывай продукты, которых нет и которые не следуют из способа приготовления"
)


class FoodItem(BaseModel):
    name: str
    weight_grams: int = Field(ge=0)
    calories: int = Field(ge=0)
    protein: int = Field(ge=0)
    fat: int = Field(ge=0)
    carbs: int = Field(ge=0)
    confidence: str = "medium"

    @field_validator("confidence")
    @classmethod
    def normalize_confidence(cls, v: str) -> str:
        v = v.lower().strip()
        if v not in {"high", "medium", "low"}:
            return "medium"
        return v


class FoodTotal(BaseModel):
    calories: int = 0
    protein: int = 0
    fat: int = 0
    carbs: int = 0


class FoodAnalysis(BaseModel):
    items: list[FoodItem] = Field(default_factory=list)
    total: FoodTotal = Field(default_factory=FoodTotal)
    comment: str = ""

    @property
    def is_food(self) -> bool:
        return len(self.items) > 0 and self.total.calories > 0


def _compress_image(image_bytes: bytes, max_side: int = 1024, quality: int = 80) -> tuple[bytes, str]:
    """Уменьшает фото — Gemini отвечает быстрее, меньше таймаутов."""
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        w, h = img.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality, optimize=True)
        return buf.getvalue(), "image/jpeg"
    except Exception as exc:
        logger.warning("Image compress failed, sending original: %s", exc)
        return image_bytes, "image/jpeg"


class GeminiVisionService:
    """Распознавание еды через Gemini API (REST)."""

    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        self.timeout = 120.0
        self.base_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )

    async def analyze_photo(
        self, image_bytes: bytes, mime_type: str = "image/jpeg"
    ) -> FoodAnalysis:
        image_bytes, mime_type = _compress_image(image_bytes)
        b64 = base64.standard_b64encode(image_bytes).decode("utf-8")
        logger.info(
            "Gemini request model=%s image_kb=%.1f",
            self.model,
            len(image_bytes) / 1024,
        )

        payload: dict[str, Any] = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64,
                            }
                        },
                        {"text": USER_PROMPT},
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }

        return await self._request(payload, retries=2)

    async def apply_correction(
        self,
        current: FoodAnalysis,
        user_text: str,
    ) -> FoodAnalysis:
        payload: dict[str, Any] = {
            "systemInstruction": {
                "parts": [
                    {
                        "text": (
                            "Ты — нутрициолог. Пользователь хочет скорректировать "
                            "предыдущий анализ еды. Верни обновлённый JSON того же "
                            "формата. Только JSON, без пояснений."
                        )
                    }
                ]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"Текущий анализ:\n{current.model_dump_json(indent=2)}\n\n"
                                f"Корректировка пользователя: «{user_text}»\n\n"
                                "Верни обновлённый JSON."
                            )
                        }
                    ],
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1024,
                "responseMimeType": "application/json",
            },
        }
        return await self._request(payload, retries=2)

    async def _request(self, payload: dict[str, Any], retries: int = 1) -> FoodAnalysis:
        params = {"key": self.api_key}
        headers = {"Content-Type": "application/json"}
        last_exc: Exception | None = None

        for attempt in range(1, retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.base_url,
                        params=params,
                        json=payload,
                        headers=headers,
                    )

                if response.status_code != 200:
                    logger.error(
                        "Gemini API error %s: %s",
                        response.status_code,
                        response.text[:500],
                    )
                    raise RuntimeError(f"Gemini API returned {response.status_code}")

                data = response.json()
                raw_text = self._extract_text(data)
                return self._parse_json(raw_text)

            except httpx.TimeoutException as exc:
                last_exc = exc
                logger.warning(
                    "Gemini timeout attempt %s/%s model=%s",
                    attempt,
                    retries,
                    self.model,
                )
                if attempt >= retries:
                    raise
            except Exception as exc:
                last_exc = exc
                raise

        raise last_exc or RuntimeError("Gemini request failed")

    def _extract_text(self, data: dict[str, Any]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            prompt_feedback = data.get("promptFeedback") or {}
            logger.error("Gemini empty candidates: %s", prompt_feedback)
            raise ValueError("Empty response from Gemini")

        parts = candidates[0].get("content", {}).get("parts") or []
        texts = [p.get("text", "") for p in parts if "text" in p]
        text = "".join(texts).strip()
        if not text:
            raise ValueError("Empty text from Gemini")
        return text

    def _parse_json(self, raw: str) -> FoodAnalysis:
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse Gemini JSON: %s\nRaw: %s", exc, raw[:400])
            raise ValueError("Invalid JSON from Gemini") from exc

        try:
            analysis = FoodAnalysis.model_validate(parsed)
        except ValidationError as exc:
            logger.error("Validation error: %s", exc)
            raise ValueError("Schema validation failed") from exc

        if analysis.items:
            analysis.total = FoodTotal(
                calories=sum(i.calories for i in analysis.items),
                protein=sum(i.protein for i in analysis.items),
                fat=sum(i.fat for i in analysis.items),
                carbs=sum(i.carbs for i in analysis.items),
            )

        return analysis
