from django.urls import path

from .views import (
    IncidentListView,
    IncomingTextMessageTestView,
    TelegramWebhookView,
)


app_name = "incidents"

urlpatterns = [
    path(
        "incidents/",
        IncidentListView.as_view(),
        name="incident-list",
    ),
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