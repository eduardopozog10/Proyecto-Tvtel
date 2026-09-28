import re
import unicodedata

from .base import AIProvider
from .schemas import IncidentExtractionResult


class MockAIProvider(AIProvider):
    EQUIPMENT_NAMES = (
        "cámara",
        "transmisor",
        "router",
        "antena",
        "monitor",
        "micrófono",
        "consola",
        "decodificador",
    )

    FAILURE_PATTERNS = (
        "no enciende",
        "sin señal",
        "se apaga",
        "no funciona",
        "imagen congelada",
        "audio cortado",
        "sobrecalentamiento",
    )

    def extract_incident(
        self,
        message: str,
        previous_data: dict | None = None,
    ) -> IncidentExtractionResult:
        previous_data = previous_data or {}
        normalized_message = self._normalize_text(message)

        unit = previous_data.get("unit") or self._extract_unit(message)
        equipment = (
            previous_data.get("equipment")
            or self._extract_equipment(normalized_message)
        )
        failure_type = (
            previous_data.get("failure_type")
            or self._extract_failure_type(normalized_message)
        )
        description = previous_data.get("description") or message.strip()
        priority = (
            previous_data.get("priority")
            or self._extract_priority(normalized_message)
        )

        extracted_data = {
            "unit": unit,
            "equipment": equipment,
            "failure_type": failure_type,
            "description": description,
            "priority": priority,
        }

        required_fields = (
            "unit",
            "equipment",
            "failure_type",
            "description",
        )

        missing_fields = [
            field_name
            for field_name in required_fields
            if not extracted_data.get(field_name)
        ]

        clarification_question = self._build_question(missing_fields)

        return IncidentExtractionResult(
            unit=unit,
            equipment=equipment,
            failure_type=failure_type,
            description=description,
            priority=priority,
            missing_fields=missing_fields,
            clarification_question=clarification_question,
            raw_response={
                "provider": "mock",
                "message": message,
            },
        )

    def _normalize_text(self, text: str):
        normalized_text = unicodedata.normalize("NFD", text.lower())

        return "".join(
            character
            for character in normalized_text
            if unicodedata.category(character) != "Mn"
        )

    def _extract_unit(self, message: str):
        normalized_message = self._normalize_text(message)

        match = re.search(
            r"\bunidad(?:\s+movil)?\s+[a-zA-Z0-9-]+",
            normalized_message,
            flags=re.IGNORECASE,
        )

        if match is None:
            return None

        return match.group(0).strip().capitalize()

    def _extract_equipment(self, normalized_message: str):
        for equipment_name in self.EQUIPMENT_NAMES:
            normalized_equipment = self._normalize_text(equipment_name)

            if normalized_equipment in normalized_message:
                return equipment_name.capitalize()

        return None

    def _extract_failure_type(self, normalized_message: str):
        for failure_pattern in self.FAILURE_PATTERNS:
            normalized_failure = self._normalize_text(failure_pattern)

            if normalized_failure in normalized_message:
                return failure_pattern.capitalize()

        return None

    def _extract_priority(self, normalized_message: str):
        critical_words = (
            "incendio",
            "humo",
            "riesgo electrico",
            "emergencia",
        )

        if any(word in normalized_message for word in critical_words):
            return "critical"

        high_words = (
            "no enciende",
            "sin senal",
            "fuera de servicio",
        )

        if any(word in normalized_message for word in high_words):
            return "high"

        return "medium"

    def _build_question(self, missing_fields: list[str]):
        if not missing_fields:
            return None

        questions = {
            "unit": "¿En qué unidad ocurrió la falla?",
            "equipment": "¿Qué equipo presenta la falla?",
            "failure_type": "¿Qué tipo de falla presenta el equipo?",
            "description": "¿Puedes describir con más detalle lo ocurrido?",
        }

        return questions[missing_fields[0]]