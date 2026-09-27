from django.urls import path

from .views import IncomingTextMessageTestView


app_name = "incidents"

urlpatterns = [
    path(
        "messages/test/",
        IncomingTextMessageTestView.as_view(),
        name="incoming-text-message-test",
    ),
]