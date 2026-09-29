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


class IncidentListViewTests(TestCase):
    def setUp(self):
        self.technician = Technician.objects.create(
            full_name="Técnico Dashboard",
            is_active=True,
        )

        self.high_incident = Incident.objects.create(
            technician=self.technician,
            unit="Unidad móvil 20",
            equipment="Cámara principal",
            failure_type="No enciende",
            description=(
                "La cámara principal de la unidad móvil 20 "
                "no enciende."
            ),
            priority=Incident.Priority.HIGH,
            status=Incident.Status.REPORTED,
            original_message=(
                "La cámara principal de la unidad móvil 20 "
                "no enciende."
            ),
        )

        self.low_incident = Incident.objects.create(
            technician=self.technician,
            unit="Unidad móvil 40",
            equipment="Cámara auxiliar",
            failure_type="Imagen intermitente",
            description=(
                "La cámara auxiliar de la unidad móvil 40 "
                "presenta una falla intermitente."
            ),
            priority=Incident.Priority.LOW,
            status=Incident.Status.REPORTED,
            original_message=(
                "La cámara auxiliar de la unidad móvil 40 "
                "presenta una falla intermitente."
            ),
        )

    def test_lists_incidents(self):
        response = self.client.get(
            "/api/v1/incidents/",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["count"],
            2,
        )
        self.assertIsNone(
            data["next"],
        )
        self.assertIsNone(
            data["previous"],
        )

        results = data["results"]

        self.assertEqual(
            len(results),
            2,
        )

        ids = {
            item["id"]
            for item in results
        }

        self.assertIn(
            self.high_incident.pk,
            ids,
        )
        self.assertIn(
            self.low_incident.pk,
            ids,
        )

    def test_filters_by_priority(self):
        response = self.client.get(
            "/api/v1/incidents/?priority=high",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["count"],
            1,
        )

        results = data["results"]

        self.assertEqual(
            len(results),
            1,
        )
        self.assertEqual(
            results[0]["id"],
            self.high_incident.pk,
        )

    def test_filters_by_status(self):
        response = self.client.get(
            "/api/v1/incidents/?status=reported",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["count"],
            2,
        )

        results = data["results"]

        self.assertEqual(
            len(results),
            2,
        )

    def test_filters_by_unit(self):
        response = self.client.get(
            "/api/v1/incidents/?unit=40",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["count"],
            1,
        )

        results = data["results"]

        self.assertEqual(
            len(results),
            1,
        )
        self.assertEqual(
            results[0]["id"],
            self.low_incident.pk,
        )

    def test_filters_by_equipment(self):
        response = self.client.get(
            "/api/v1/incidents/?equipment=auxiliar",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["count"],
            1,
        )

        results = data["results"]

        self.assertEqual(
            len(results),
            1,
        )
        self.assertEqual(
            results[0]["id"],
            self.low_incident.pk,
        )

    def test_combines_status_and_priority_filters(self):
        response = self.client.get(
            "/api/v1/incidents/"
            "?status=reported&priority=low",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["count"],
            1,
        )

        results = data["results"]

        self.assertEqual(
            len(results),
            1,
        )
        self.assertEqual(
            results[0]["id"],
            self.low_incident.pk,
        )

    def test_searches_incidents_by_text(self):
        response = self.client.get(
            "/api/v1/incidents/?search=intermitente",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()

        self.assertEqual(
            data["count"],
            1,
        )

        results = data["results"]

        self.assertEqual(
            len(results),
            1,
        )
        self.assertEqual(
            results[0]["id"],
            self.low_incident.pk,
        )
        self.assertEqual(
            results[0]["failure_type"],
            "Imagen intermitente",
        )

    def test_orders_incidents_by_created_at_ascending(self):
        response = self.client.get(
            "/api/v1/incidents/?ordering=created_at",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()
        results = data["results"]

        self.assertEqual(
            results[0]["id"],
            self.high_incident.pk,
        )
        self.assertEqual(
            results[1]["id"],
            self.low_incident.pk,
        )

    def test_orders_incidents_by_created_at_descending(self):
        response = self.client.get(
            "/api/v1/incidents/?ordering=-created_at",
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        data = response.json()
        results = data["results"]

        self.assertEqual(
            results[0]["id"],
            self.low_incident.pk,
        )
        self.assertEqual(
            results[1]["id"],
            self.high_incident.pk,
        )  