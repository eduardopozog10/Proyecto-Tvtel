from django.urls import path

from .views import (
    IncomingTextMessageTestView,
    TelegramWebhookView,
)


app_name = "incidents"

urlpatterns = [
    path(
        "messages/test/",
        IncomingTextMessageTestView.as_view(),
        name="incoming-text-message-test",
    ),
    path(
        "messaging/telegram/webhook/",
        TelegramWebhookView.as_view(),
        name="telegram-webhook",
    ),
]