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
            "intent": {
                "type": "string",
                "enum": [
                    "incident_report",
                    "incident_followup",
                    "conversation",
                ],
                "description": (
                    "Intención principal del mensaje del técnico."
                ),
            },
            "conversation_reply": {
                "type": ["string", "null"],
                "description": (
                    "Respuesta conversacional cuando el mensaje no "
                    "corresponde a información de un incidente."
                ),
            },
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
                    "Síntoma observable reportado por el técnico, "
                    "sin emitir un diagnóstico."
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
            "clarification_question": {
                "type": ["string", "null"],
                "description": (
                    "Pregunta breve y natural para solicitar el siguiente "
                    "dato faltante del incidente."
                ),
            },
        },
        "required": [
            "intent",
            "conversation_reply",
            "unit",
            "equipment",
            "failure_type",
            "description",
            "priority",
            "clarification_question",
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

        intent = self._normalize_intent(
            response_data.get("intent")
        )

        conversation_reply = self._clean_text(
            response_data.get("conversation_reply")
        )

        if intent == "conversation":
            return IncidentExtractionResult(
                intent=intent,
                conversation_reply=conversation_reply,
                missing_fields=[],
                clarification_question=None,
                raw_response={
                    "provider": "gemini",
                    "model": self.model,
                    "data": response_data,
                },
            )

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

        clarification_question = None

        if missing_fields:
            clarification_question = self._clean_text(
                response_data.get("clarification_question")
            )

            if not clarification_question:
                clarification_question = (
                    self._build_fallback_question(
                        missing_fields
                    )
                )

        return IncidentExtractionResult(
            intent=intent,
            conversation_reply=None,
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

        has_previous_data = bool(previous_data)

        return f"""
Eres el asistente técnico conversacional de TVTEL.

Tu función principal es conversar de manera natural con técnicos,
identificar reportes de incidentes, recopilar los datos necesarios
para registrarlos y responder mensajes generales cuando no se trate
de una falla.

Debes mantener siempre un tono:
- Formal.
- Cordial.
- Profesional.
- Claro.
- Simple.
- Natural.
- Breve.

Evita sonar como un bot rígido.
No repitas siempre las mismas frases.
Puedes variar tu vocabulario y la estructura de las respuestas,
manteniendo siempre un lenguaje sencillo y profesional.

Debes clasificar cada mensaje en una de estas intenciones:

1. incident_report
   El técnico está comenzando a informar una falla o incidente.

2. incident_followup
   El técnico está entregando información para completar un
   incidente que ya estaba en conversación.

3. conversation
   El mensaje es conversación general, saludo, agradecimiento,
   comentario, pregunta que no entrega información del incidente,
   o cualquier mensaje que no deba almacenarse como reporte técnico.

Hay datos anteriores del incidente: {has_previous_data}

Reglas de conversación:
- Si el técnico saluda, responde al saludo de forma natural.
- Si agradece, responde cordialmente.
- Si realiza conversación general, responde brevemente y con tono
  profesional.
- Si pregunta qué puedes hacer, explica brevemente que puedes ayudar
  a registrar y dar seguimiento a incidentes técnicos.
- No fuerces una conversación general para convertirla en incidente.
- Un mensaje de conversación debe usar intent="conversation".
- Para intent="conversation", utiliza conversation_reply.
- Para intent="conversation", los campos del incidente deben ser null.
- Para intent="conversation", clarification_question debe ser null.
- No inventes información sobre TVTEL.
- No inventes procedimientos internos, personas, horarios ni políticas.
- Si no puedes responder algo con seguridad, indícalo de forma breve.

Reglas de incidentes:
- No inventes información.
- No entregues recomendaciones de reparación.
- No emitas diagnósticos técnicos definitivos.
- Extrae solamente información explícita o directamente observable
  en lo dicho por el técnico.
- El campo failure_type representa el síntoma observable, no una
  causa técnica inventada.
- Conserva los datos anteriores cuando el mensaje actual solo
  responda una pregunta pendiente.
- Si existe información anterior y el mensaje actual completa,
  corrige o amplía el incidente, usa intent="incident_followup".
- Si el técnico claramente inicia una falla nueva, utiliza
  intent="incident_report".
- Si un dato realmente no está disponible, devuelve null.
- La descripción debe conservar el sentido completo de lo reportado.
- No elimines información válida obtenida anteriormente.
- Si el técnico corrige explícitamente un dato anterior, utiliza
  el dato corregido.

Reglas para failure_type:
- Frases como "no enciende", "no muestra imagen", "sin audio",
  "pantalla negra", "imagen intermitente", "se reinicia",
  "no responde", "sin señal" o expresiones equivalentes son
  síntomas válidos.
- No devuelvas null en failure_type si el técnico ya explicó
  claramente el comportamiento anormal.
- Puedes resumir el síntoma en una frase breve y objetiva.
- No conviertas síntomas en diagnósticos.
- Ejemplo válido:
  "no muestra imagen" -> "No muestra imagen"
- Ejemplo no válido:
  "no muestra imagen" -> "Tarjeta de video dañada"

Reglas de prioridad:
- critical:
  incendio, humo, riesgo eléctrico, peligro para personas o
  emergencia explícita.
- high:
  equipo completamente fuera de servicio, no enciende, pérdida
  total de señal o pérdida completa de su función principal.
- medium:
  falla operativa normal sin riesgo inmediato.
- low:
  problema menor que permite continuar operando.

Reglas para preguntas de aclaración:
- Si falta información necesaria para crear el incidente, genera
  clarification_question.
- Realiza solo una pregunta a la vez.
- Pregunta primero por el dato faltante más importante.
- La pregunta debe ser breve, clara y natural.
- Mantén un tono formal y cordial.
- No utilices siempre la misma redacción.
- No hagas una lista de preguntas.
- No pidas información que ya fue entregada.
- Si no falta ningún dato, clarification_question debe ser null.

Los datos necesarios para registrar un incidente son:
- unit
- equipment
- failure_type
- description

Ejemplos de preguntas válidas:
- "¿Me puedes indicar en qué unidad ocurrió la falla?"
- "Para completar el reporte, ¿en qué unidad se encuentra el equipo?"
- "¿Qué equipo está presentando el problema?"
- "¿Qué comportamiento anormal presenta el equipo?"
- "¿Puedes describirme brevemente qué ocurrió?"

Ejemplos conversacionales:

Mensaje:
"Hola, buenos días"

Resultado esperado:
intent = "conversation"
conversation_reply = una respuesta cordial al saludo
No crear información de incidente.

Mensaje:
"Gracias"

Resultado esperado:
intent = "conversation"
conversation_reply = una respuesta breve y cordial.

Mensaje:
"Tengo una cámara que no muestra imagen"

Resultado esperado:
intent = "incident_report"
equipment = "Cámara"
failure_type = "No muestra imagen"
Preguntar solamente por el siguiente dato necesario.

Mensaje:
"Es en la móvil 8"

Si existe un incidente pendiente:
intent = "incident_followup"
unit = "Móvil 8"
Conservar los demás datos anteriores.

Mensaje:
"Un momento, estoy revisando"

Resultado esperado:
intent = "conversation"
Responder naturalmente.
No utilizar esa frase como descripción, falla, equipo ni unidad.
No borrar los datos anteriores del incidente.

Datos anteriores del incidente:
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

    def _normalize_intent(self, value):
        if not isinstance(value, str):
            return "incident_report"

        normalized_value = value.strip().lower()

        valid_intents = {
            "incident_report",
            "incident_followup",
            "conversation",
        }

        if normalized_value not in valid_intents:
            return "incident_report"

        return normalized_value

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

    def _build_fallback_question(
        self,
        missing_fields: list[str],
    ):
        if not missing_fields:
            return None

        questions = {
            "unit": (
                "¿Me puedes indicar en qué unidad ocurrió la falla?"
            ),
            "equipment": (
                "¿Qué equipo está presentando la falla?"
            ),
            "failure_type": (
                "¿Qué comportamiento anormal presenta el equipo?"
            ),
            "description": (
                "¿Puedes describirme brevemente qué ocurrió?"
            ),
        }

        return questions[missing_fields[0]]