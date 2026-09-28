from django.utils import timezone

from incidents.messaging.factory import get_messaging_provider
from incidents.models import ChannelMessage
from incidents.services.incoming_message_service import (
    ChannelNotAuthorizedError,
    IncomingMessageService,
)


class TelegramUpdateHandler:
    PROVIDER = "telegram"

    def __init__(
        self,
        messaging_provider=None,
        incoming_service=None,
    ):
        self.messaging_provider = (
            messaging_provider
            or get_messaging_provider(self.PROVIDER)
        )
        self.incoming_service = (
            incoming_service
            or IncomingMessageService()
        )

    def handle(self, update: dict) -> dict:
        telegram_message = update.get("message")

        if telegram_message is None:
            return {
                "action": "ignored",
                "reason": "La actualización no contiene un mensaje.",
            }

        sender = telegram_message.get("from", {})
        chat = telegram_message.get("chat", {})

        external_user_id = str(sender.get("id", "")).strip()
        external_chat_id = str(chat.get("id", "")).strip()
        telegram_message_id = telegram_message.get("message_id")
        text = telegram_message.get("text")

        if (
            not external_user_id
            or not external_chat_id
            or telegram_message_id is None
        ):
            return {
                "action": "ignored",
                "reason": "El mensaje no contiene identificadores válidos.",
            }

        if text == "/start":
            self.messaging_provider.send_text(
                external_chat_id,
                (
                    "Hola. Soy el asistente de reportes técnicos "
                    "de TVTEL.\n\n"
                    "Describe la falla indicando la unidad, "
                    "el equipo y lo ocurrido."
                ),
            )

            return {
                "action": "welcome_sent",
            }

        if not isinstance(text, str) or not text.strip():
            self.messaging_provider.send_text(
                external_chat_id,
                (
                    "Por ahora solo puedo recibir reportes "
                    "escritos en texto."
                ),
            )

            return {
                "action": "unsupported_message",
            }

        external_message_id = (
            f"{external_chat_id}:{telegram_message_id}"
        )

        try:
            result = self.incoming_service.process_text(
                provider=self.PROVIDER,
                external_user_id=external_user_id,
                external_chat_id=external_chat_id,
                external_message_id=external_message_id,
                text=text,
                raw_payload=update,
            )
        except ChannelNotAuthorizedError:
            self.messaging_provider.send_text(
                external_chat_id,
                (
                    "Tu cuenta de Telegram no está autorizada "
                    "para registrar incidentes."
                ),
            )

            return {
                "action": "unauthorized_user",
            }
        except Exception:
            self.messaging_provider.send_text(
                external_chat_id,
                (
                    "No fue posible procesar el reporte en este "
                    "momento. Inténtalo nuevamente más tarde."
                ),
            )

            return {
                "action": "processing_failed",
            }

        incoming_message = result["message"]

        if result["duplicate"]:
            return {
                "action": "duplicate_message",
                "message_id": incoming_message.pk,
            }

        processing_result = result["processing"]
        reply_text = processing_result["reply"]

        try:
            telegram_response = (
                self.messaging_provider.send_text(
                    external_chat_id,
                    reply_text,
                )
            )
        except Exception as error:
            self._record_failed_reply(
                incoming_message=incoming_message,
                reply_text=reply_text,
                error=error,
            )

            return {
                "action": "reply_failed",
                "message_id": incoming_message.pk,
            }

        outgoing_message = self._record_sent_reply(
            incoming_message=incoming_message,
            reply_text=reply_text,
            telegram_response=telegram_response,
        )

        return {
            "action": processing_result["action"],
            "incoming_message_id": incoming_message.pk,
            "outgoing_message_id": outgoing_message.pk,
            "incident_created": processing_result[
                "incident_created"
            ],
        }

    def _record_sent_reply(
        self,
        *,
        incoming_message: ChannelMessage,
        reply_text: str,
        telegram_response: dict,
    ) -> ChannelMessage:
        telegram_result = telegram_response["result"]
        telegram_message_id = telegram_result["message_id"]

        external_message_id = (
            f"{incoming_message.external_chat_id}:"
            f"{telegram_message_id}"
        )

        return ChannelMessage.objects.create(
            provider=self.PROVIDER,
            external_message_id=external_message_id,
            external_sender_id=str(
                telegram_result.get("from", {}).get(
                    "id",
                    "bot",
                )
            ),
            external_chat_id=(
                incoming_message.external_chat_id
            ),
            channel_account=(
                incoming_message.channel_account
            ),
            technician=incoming_message.technician,
            incident=incoming_message.incident,
            draft=incoming_message.draft,
            direction=ChannelMessage.Direction.OUTBOUND,
            message_type=ChannelMessage.MessageType.TEXT,
            content=reply_text,
            raw_payload=telegram_response,
            status=ChannelMessage.Status.SENT,
            processed_at=timezone.now(),
        )

    def _record_failed_reply(
        self,
        *,
        incoming_message: ChannelMessage,
        reply_text: str,
        error: Exception,
    ) -> ChannelMessage:
        return ChannelMessage.objects.create(
            provider=self.PROVIDER,
            external_message_id=None,
            external_sender_id="bot",
            external_chat_id=(
                incoming_message.external_chat_id
            ),
            channel_account=(
                incoming_message.channel_account
            ),
            technician=incoming_message.technician,
            incident=incoming_message.incident,
            draft=incoming_message.draft,
            direction=ChannelMessage.Direction.OUTBOUND,
            message_type=ChannelMessage.MessageType.TEXT,
            content=reply_text,
            raw_payload={},
            status=ChannelMessage.Status.FAILED,
            error_message=str(error),
            processed_at=timezone.now(),
        )