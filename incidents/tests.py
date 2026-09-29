from django.test import TestCase, override_settings

from incidents.models import (
    ChannelMessage,
    Incident,
    IncidentDraft,
    Technician,
    TechnicianChannel,
)
from incidents.services.incoming_message_service import (
    IncomingMessageService,
)


@override_settings(AI_PROVIDER="mock")
class IncomingMessageServiceTests(TestCase):
    def setUp(self):
        self.technician = Technician.objects.create(
            full_name="Técnico de prueba",
            is_active=True,
        )

        self.channel = TechnicianChannel.objects.create(
            technician=self.technician,
            provider=TechnicianChannel.Provider.TELEGRAM,
            external_user_id="123456789",
            external_chat_id="123456789",
            is_active=True,
        )

        self.service = IncomingMessageService()

    def test_creates_incident_from_complete_message(self):
        result = self.service.process_text(
            provider="telegram",
            external_user_id="123456789",
            external_chat_id="123456789",
            external_message_id="123456789:1",
            text=(
                "La cámara de la unidad móvil 9 no enciende"
            ),
            raw_payload={
                "test": True,
            },
        )

        self.assertFalse(result["duplicate"])

        processing = result["processing"]

        self.assertEqual(
            processing["action"],
            "incident_created",
        )
        self.assertTrue(
            processing["incident_created"],
        )

        incident = Incident.objects.get()

        self.assertEqual(
            incident.technician,
            self.technician,
        )
        self.assertEqual(
            incident.unit,
            "Unidad movil 9",
        )
        self.assertEqual(
            incident.equipment,
            "Cámara",
        )
        self.assertEqual(
            incident.failure_type,
            "No enciende",
        )
        self.assertEqual(
            incident.priority,
            Incident.Priority.HIGH,
        )

        message = ChannelMessage.objects.get(
            direction=ChannelMessage.Direction.INBOUND,
        )

        self.assertEqual(
            message.status,
            ChannelMessage.Status.PROCESSED,
        )
        self.assertEqual(
            message.incident,
            incident,
        )

    def test_duplicate_message_is_not_processed_twice(self):
        first_result = self.service.process_text(
            provider="telegram",
            external_user_id="123456789",
            external_chat_id="123456789",
            external_message_id="123456789:2",
            text=(
                "La cámara de la unidad móvil 10 no enciende"
            ),
            raw_payload={
                "test": True,
            },
        )

        second_result = self.service.process_text(
            provider="telegram",
            external_user_id="123456789",
            external_chat_id="123456789",
            external_message_id="123456789:2",
            text=(
                "La cámara de la unidad móvil 10 no enciende"
            ),
            raw_payload={
                "test": True,
            },
        )

        self.assertFalse(
            first_result["duplicate"],
        )
        self.assertTrue(
            second_result["duplicate"],
        )
        self.assertIsNone(
            second_result["processing"],
        )

        self.assertEqual(
            Incident.objects.count(),
            1,
        )
        self.assertEqual(
            ChannelMessage.objects.filter(
                provider="telegram",
                external_message_id="123456789:2",
            ).count(),
            1,
        )

    def test_creates_draft_when_information_is_missing(self):
        result = self.service.process_text(
            provider="telegram",
            external_user_id="123456789",
            external_chat_id="123456789",
            external_message_id="123456789:3",
            text="La consola no funciona",
            raw_payload={
                "test": True,
            },
        )

        processing = result["processing"]

        self.assertEqual(
            processing["action"],
            "ask_clarification",
        )
        self.assertFalse(
            processing["incident_created"],
        )
        self.assertIn(
            "unit",
            processing["missing_fields"],
        )

        self.assertEqual(
            Incident.objects.count(),
            0,
        )

        draft = IncidentDraft.objects.get()

        self.assertEqual(
            draft.status,
            IncidentDraft.Status.COLLECTING,
        )
        self.assertIn(
            "unit",
            draft.missing_fields,
        )

    def test_completes_existing_draft_with_second_message(self):
        first_result = self.service.process_text(
            provider="telegram",
            external_user_id="123456789",
            external_chat_id="123456789",
            external_message_id="123456789:4",
            text="La consola no funciona",
            raw_payload={
                "test": True,
            },
        )

        draft_id = first_result["processing"]["draft_id"]

        second_result = self.service.process_text(
            provider="telegram",
            external_user_id="123456789",
            external_chat_id="123456789",
            external_message_id="123456789:5",
            text="Unidad móvil 12",
            raw_payload={
                "test": True,
            },
        )

        processing = second_result["processing"]

        self.assertEqual(
            processing["action"],
            "incident_created",
        )
        self.assertTrue(
            processing["incident_created"],
        )

        self.assertEqual(
            Incident.objects.count(),
            1,
        )

        incident = Incident.objects.get()

        self.assertEqual(
            incident.unit,
            "Unidad movil 12",
        )
        self.assertEqual(
            incident.equipment,
            "Consola",
        )
        self.assertEqual(
            incident.failure_type,
            "No funciona",
        )

        draft = IncidentDraft.objects.get(
            pk=draft_id,
        )

        self.assertEqual(
            draft.status,
            IncidentDraft.Status.COMPLETED,
        )
        self.assertEqual(
            draft.incident,
            incident,
        )
        self.assertEqual(
            draft.missing_fields,
            [],
        )