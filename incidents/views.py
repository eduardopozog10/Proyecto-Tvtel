from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from incidents.models import ChannelMessage, TechnicianChannel
from incidents.serializers import IncomingTextMessageSerializer
from incidents.services.incident_processor import IncidentProcessor


class IncomingTextMessageTestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = IncomingTextMessageSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        provider = serializer.validated_data["provider"]
        external_user_id = serializer.validated_data[
            "external_user_id"
        ]
        external_chat_id = serializer.validated_data[
            "external_chat_id"
        ]
        external_message_id = serializer.validated_data[
            "external_message_id"
        ]
        text = serializer.validated_data["text"]

        channel_account = (
            TechnicianChannel.objects.select_related("technician")
            .filter(
                provider=provider,
                external_user_id=external_user_id,
                is_active=True,
                technician__is_active=True,
            )
            .first()
        )

        if channel_account is None:
            return Response(
                {
                    "detail": (
                        "No existe un técnico activo asociado "
                        "a este usuario y proveedor."
                    )
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        existing_message = ChannelMessage.objects.filter(
            provider=provider,
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

        message = ChannelMessage.objects.create(
            provider=provider,
            external_message_id=external_message_id,
            external_sender_id=external_user_id,
            external_chat_id=external_chat_id,
            channel_account=channel_account,
            technician=channel_account.technician,
            direction=ChannelMessage.Direction.INBOUND,
            message_type=ChannelMessage.MessageType.TEXT,
            content=text,
            raw_payload=request.data,
            status=ChannelMessage.Status.RECEIVED,
        )

        try:
            processing_result = IncidentProcessor().process(message)

        except Exception as error:
            message.status = ChannelMessage.Status.FAILED
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
                "provider": provider,
                "processing": processing_result,
            },
            status=status.HTTP_201_CREATED,
        )