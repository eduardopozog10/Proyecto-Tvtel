import uuid

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Technician, WhatsAppMessage
from .serializers import IncomingTextMessageSerializer


class IncomingTextMessageTestView(APIView):
    def post(self, request):
        serializer = IncomingTextMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        phone_number = serializer.validated_data["phone_number"]
        text = serializer.validated_data["text"]

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

        external_message_id = serializer.validated_data.get(
            "external_message_id"
        )

        if not external_message_id:
            external_message_id = f"test-{uuid.uuid4()}"

        existing_message = WhatsAppMessage.objects.filter(
            external_message_id=external_message_id
        ).first()

        if existing_message is not None:
            return Response(
                {
                    "detail": "El mensaje ya había sido recibido.",
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
            raw_payload=serializer.validated_data,
            status=WhatsAppMessage.Status.RECEIVED,
        )

        return Response(
            {
                "detail": "Mensaje recibido y almacenado correctamente.",
                "duplicate": False,
                "message": {
                    "id": message.pk,
                    "external_message_id": message.external_message_id,
                    "technician": technician.full_name,
                    "phone_number": message.phone_number,
                    "content": message.content,
                    "status": message.status,
                },
            },
            status=status.HTTP_201_CREATED,
        )