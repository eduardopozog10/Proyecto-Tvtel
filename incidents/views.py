from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from incidents.messaging.telegram_update_handler import (
    TelegramUpdateHandler,
)
from incidents.models import Incident
from incidents.serializers import (
    IncidentSerializer,
    IncomingTextMessageSerializer,
)
from incidents.services.incoming_message_service import (
    ChannelNotAuthorizedError,
    IncomingMessageService,
)


class IncidentListView(generics.ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = IncidentSerializer

    def get_queryset(self):
        return (
            Incident.objects.select_related(
                "technician"
            )
            .order_by("-created_at")
        )


class IncomingTextMessageTestView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = IncomingTextMessageSerializer(
            data=request.data,
        )
        serializer.is_valid(raise_exception=True)

        validated_data = serializer.validated_data

        try:
            result = IncomingMessageService().process_text(
                provider=validated_data["provider"],
                external_user_id=validated_data[
                    "external_user_id"
                ],
                external_chat_id=validated_data[
                    "external_chat_id"
                ],
                external_message_id=validated_data[
                    "external_message_id"
                ],
                text=validated_data["text"],
                raw_payload=request.data,
            )
        except ChannelNotAuthorizedError as error:
            return Response(
                {
                    "detail": str(error),
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as error:
            return Response(
                {
                    "detail": (
                        "No fue posible procesar el mensaje."
                    ),
                    "error": str(error),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        message = result["message"]

        if result["duplicate"]:
            return Response(
                {
                    "message": (
                        "El mensaje ya había sido recibido."
                    ),
                    "duplicate": True,
                    "message_id": message.pk,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "message": "Mensaje recibido y procesado.",
                "duplicate": False,
                "message_id": message.pk,
                "provider": message.provider,
                "processing": result["processing"],
            },
            status=status.HTTP_201_CREATED,
        )


class TelegramWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            result = TelegramUpdateHandler().handle(
                request.data,
            )
        except Exception:
            return Response(
                {
                    "detail": (
                        "No fue posible procesar la actualización "
                        "de Telegram."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {
                "ok": True,
                "result": result,
            },
            status=status.HTTP_200_OK,
        )