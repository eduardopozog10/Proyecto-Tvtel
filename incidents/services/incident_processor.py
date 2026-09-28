from django.db import transaction
from django.utils import timezone

from incidents.ai.factory import get_ai_provider
from incidents.models import (
    ChannelMessage,
    Incident,
    IncidentDraft,
)


class IncidentProcessor:
    REQUIRED_FIELDS = (
        "unit",
        "equipment",
        "failure_type",
        "description",
    )

    FALLBACK_QUESTIONS = {
        "unit": "¿En qué unidad ocurrió la falla?",
        "equipment": "¿Qué equipo presenta la falla?",
        "failure_type": "¿Qué tipo de falla presenta el equipo?",
        "description": "¿Puedes describir con más detalle lo ocurrido?",
    }

    def __init__(self, ai_provider=None):
        self.ai_provider = ai_provider or get_ai_provider()

    @transaction.atomic
    def process(self, message: ChannelMessage):
        if message.technician is None:
            raise ValueError(
                "El mensaje debe estar asociado a un técnico."
            )

        message.status = ChannelMessage.Status.PROCESSING
        message.save(update_fields=["status"])

        draft = (
            IncidentDraft.objects.filter(
                technician=message.technician,
                status__in=[
                    IncidentDraft.Status.COLLECTING,
                    IncidentDraft.Status.READY,
                ],
            )
            .order_by("-updated_at")
            .first()
        )

        previous_data = draft.extracted_data if draft else {}

        extraction = self.ai_provider.extract_incident(
            message=message.content,
            previous_data=previous_data,
        )

        extracted_data = {
            "unit": extraction.unit or previous_data.get("unit"),
            "equipment": (
                extraction.equipment
                or previous_data.get("equipment")
            ),
            "failure_type": (
                extraction.failure_type
                or previous_data.get("failure_type")
            ),
            "description": (
                extraction.description
                or previous_data.get("description")
            ),
            "priority": (
                extraction.priority
                or previous_data.get("priority")
                or Incident.Priority.MEDIUM
            ),
        }

        valid_priorities = {
            choice[0]
            for choice in Incident.Priority.choices
        }

        if extracted_data["priority"] not in valid_priorities:
            extracted_data["priority"] = Incident.Priority.MEDIUM

        missing_fields = [
            field_name
            for field_name in self.REQUIRED_FIELDS
            if not extracted_data.get(field_name)
        ]

        clarification_question = extraction.clarification_question

        if missing_fields and not clarification_question:
            clarification_question = self.FALLBACK_QUESTIONS[
                missing_fields[0]
            ]

        if draft is None:
            draft = IncidentDraft.objects.create(
                technician=message.technician,
                initial_message=message,
                extracted_data=extracted_data,
                missing_fields=missing_fields,
                last_question=clarification_question or "",
                status=(
                    IncidentDraft.Status.COLLECTING
                    if missing_fields
                    else IncidentDraft.Status.READY
                ),
            )
        else:
            draft.extracted_data = extracted_data
            draft.missing_fields = missing_fields
            draft.last_question = clarification_question or ""
            draft.status = (
                IncidentDraft.Status.COLLECTING
                if missing_fields
                else IncidentDraft.Status.READY
            )
            draft.save(
                update_fields=[
                    "extracted_data",
                    "missing_fields",
                    "last_question",
                    "status",
                    "updated_at",
                ]
            )

        message.draft = draft

        if missing_fields:
            message.status = ChannelMessage.Status.PROCESSED
            message.processed_at = timezone.now()
            message.save(
                update_fields=[
                    "draft",
                    "status",
                    "processed_at",
                ]
            )

            return {
                "action": "ask_clarification",
                "incident_created": False,
                "draft_id": draft.pk,
                "missing_fields": missing_fields,
                "reply": clarification_question,
                "extracted_data": extracted_data,
            }

        initial_message_content = ""

        if draft.initial_message is not None:
            initial_message_content = draft.initial_message.content

        incident = Incident.objects.create(
            technician=message.technician,
            unit=extracted_data["unit"],
            equipment=extracted_data["equipment"],
            failure_type=extracted_data["failure_type"],
            description=extracted_data["description"],
            priority=extracted_data["priority"],
            status=Incident.Status.REPORTED,
            original_message=initial_message_content,
        )

        draft.incident = incident
        draft.status = IncidentDraft.Status.COMPLETED
        draft.missing_fields = []
        draft.last_question = ""
        draft.completed_at = timezone.now()
        draft.save(
            update_fields=[
                "incident",
                "status",
                "missing_fields",
                "last_question",
                "completed_at",
                "updated_at",
            ]
        )

        ChannelMessage.objects.filter(
            draft=draft,
        ).update(
            incident=incident,
        )

        message.incident = incident
        message.status = ChannelMessage.Status.PROCESSED
        message.processed_at = timezone.now()
        message.save(
            update_fields=[
                "draft",
                "incident",
                "status",
                "processed_at",
            ]
        )

        return {
            "action": "incident_created",
            "incident_created": True,
            "incident_id": incident.pk,
            "incident_code": incident.code,
            "reply": (
                f"Reporte {incident.code} creado correctamente."
            ),
            "extracted_data": extracted_data,
        }