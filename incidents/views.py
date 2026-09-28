from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from incidents.models import Technician, WhatsAppMessage
from incidents.serializers import IncomingTextMessageSerializer
from incidents.services.incident_processor import IncidentProcessor


class IncomingTextMessageTestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = IncomingTextMessageSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        text = serializer.validated_data["text"]
        external_message_id = serializer.validated_data[
            "external_message_id"
        ]

        technician = Technician.objects.filter(
            whatsapp_number=phone_number,
            is_active=True,
        ).first()

        if technician is None:
            return Response(
                {
                    "detail": (
                        "No existe un técnico activo asociado "
                        "a este número de WhatsApp."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        existing_message = WhatsAppMessage.objects.filter(
            external_message_id=external_message_id,
        ).first()

        if existing_message is not None:
            return Response(
                {
                    "message": "El mensaje ya había sido recibido.",
                    "duplicate": True,
                    "message_id": existing_message.pk,
                },
                status=status.HTTP_200_OK,
            )

        message = WhatsAppMessage.objects.create(
            external_message_id=external_message_id,
            technician=technician,
            phone_number=phone_number,
            direction=WhatsAppMessage.Direction.INBOUND,
            message_type=WhatsAppMessage.MessageType.TEXT,
            content=text,
            raw_payload=request.data,
            status=WhatsAppMessage.Status.RECEIVED,
        )

        try:
            processing_result = IncidentProcessor().process(message)

        except Exception as error:
            message.status = WhatsAppMessage.Status.FAILED
            message.error_message = str(error)
            message.save(
                update_fields=[
                    "status",
                    "error_message",
                ]
            )

            return Response(
                {
                    "detail": "No fue posible procesar el mensaje.",
                    "message_id": message.pk,
                    "error": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "message": "Mensaje recibido y procesado.",
                "duplicate": False,
                "message_id": message.pk,
                "processing": processing_result,
            },
            status=status.HTTP_201_CREATED,
        )