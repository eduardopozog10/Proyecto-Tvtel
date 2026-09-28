import json

from django.conf import settings
from google import genai

from .base import AIProvider
from .schemas import IncidentExtractionResult


class GeminiAIProvider(AIProvider):
    REQUIRED_FIELDS = (
        "unit",
        "equipment",
        "failure_type",
        "description",
    )

    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "unit": {
                "type": ["string", "null"],
                "description": (
                    "Unidad, móvil, estudio o ubicación donde ocurrió "
                    "la falla."
                ),
            },
            "equipment": {
                "type": ["string", "null"],
                "description": "Equipo que presenta la falla.",
            },
            "failure_type": {
                "type": ["string", "null"],
                "description": (
                    "Síntoma o tipo de falla, sin emitir un diagnóstico."
                ),
            },
            "description": {
                "type": ["string", "null"],
                "description": (
                    "Descripción objetiva de lo reportado por el técnico."
                ),
            },
            "priority": {
                "type": ["string", "null"],
                "description": (
                    "Prioridad: low, medium, high o critical."
                ),
            },
        },
        "required": [
            "unit",
            "equipment",
            "failure_type",
            "description",
            "priority",
        ],
    }

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY no está configurada."
            )

        self.model = settings.GEMINI_MODEL
        self.client = genai.Client(
            api_key=settings.GEMINI_API_KEY,
        )

    def extract_incident(
        self,
        message: str,
        previous_data: dict | None = None,
    ) -> IncidentExtractionResult:
        previous_data = previous_data or {}

        prompt = self._build_prompt(
            message=message,
            previous_data=previous_data,
        )

        interaction = self.client.interactions.create(
            model=self.model,
            input=prompt,
            response_format={
                "type": "text",
                "mime_type": "application/json",
                "schema": self.RESPONSE_SCHEMA,
            },
        )

        response_text = interaction.output_text

        if not response_text:
            raise ValueError(
                "Gemini devolvió una respuesta vacía."
            )

        try:
            response_data = json.loads(response_text)
        except json.JSONDecodeError as error:
            raise ValueError(
                "Gemini devolvió un JSON inválido."
            ) from error

        unit = (
            self._clean_text(response_data.get("unit"))
            or previous_data.get("unit")
        )
        equipment = (
            self._clean_text(response_data.get("equipment"))
            or previous_data.get("equipment")
        )
        failure_type = (
            self._clean_text(response_data.get("failure_type"))
            or previous_data.get("failure_type")
        )
        description = (
            self._clean_text(response_data.get("description"))
            or previous_data.get("description")
            or message.strip()
        )
        priority = self._normalize_priority(
            response_data.get("priority")
            or previous_data.get("priority")
        )

        extracted_data = {
            "unit": unit,
            "equipment": equipment,
            "failure_type": failure_type,
            "description": description,
            "priority": priority,
        }

        missing_fields = [
            field_name
            for field_name in self.REQUIRED_FIELDS
            if not extracted_data.get(field_name)
        ]

        clarification_question = self._build_question(
            missing_fields
        )

        return IncidentExtractionResult(
            unit=unit,
            equipment=equipment,
            failure_type=failure_type,
            description=description,
            priority=priority,
            missing_fields=missing_fields,
            clarification_question=clarification_question,
            raw_response={
                "provider": "gemini",
                "model": self.model,
                "data": response_data,
            },
        )

    def _build_prompt(
        self,
        message: str,
        previous_data: dict,
    ):
        previous_data_json = json.dumps(
            previous_data,
            ensure_ascii=False,
        )

        return f"""
Eres un sistema de extracción de reportes técnicos para TVTEL.

Analiza el mensaje de un técnico y devuelve únicamente los datos
solicitados por el esquema JSON.

Reglas obligatorias:
- No inventes información.
- No entregues recomendaciones de reparación.
- No emitas diagnósticos técnicos definitivos.
- El tipo de falla debe describir solamente el síntoma observado.
- Conserva los datos anteriores cuando el mensaje actual solo
  responda una pregunta pendiente.
- Si un dato no está disponible, devuelve null.
- La prioridad debe ser low, medium, high o critical.
- Usa critical solo ante incendios, humo, riesgo eléctrico,
  peligro para personas o una emergencia explícita.
- Usa high si el equipo quedó fuera de servicio, no enciende
  o perdió completamente la señal.
- Usa medium para fallas normales sin riesgo inmediato.
- Usa low para problemas menores que no impiden operar.

Datos anteriores:
{previous_data_json}

Mensaje actual del técnico:
{message}
""".strip()

    def _clean_text(self, value):
        if not isinstance(value, str):
            return None

        clean_value = value.strip()

        if not clean_value:
            return None

        return clean_value

    def _normalize_priority(self, value):
        if not isinstance(value, str):
            return "medium"

        normalized_value = value.strip().lower()

        priorities = {
            "low": "low",
            "baja": "low",
            "medium": "medium",
            "media": "medium",
            "high": "high",
            "alta": "high",
            "critical": "critical",
            "critica": "critical",
            "crítica": "critical",
        }

        return priorities.get(
            normalized_value,
            "medium",
        )

    def _build_question(self, missing_fields: list[str]):
        if not missing_fields:
            return None

        questions = {
            "unit": "¿En qué unidad ocurrió la falla?",
            "equipment": "¿Qué equipo presenta la falla?",
            "failure_type": (
                "¿Qué falla o síntoma presenta el equipo?"
            ),
            "description": (
                "¿Puedes describir con más detalle lo ocurrido?"
            ),
        }

        return questions[missing_fields[0]]