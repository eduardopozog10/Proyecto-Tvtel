from rest_framework import serializers

from incidents.models import TechnicianChannel


class IncomingTextMessageSerializer(serializers.Serializer):
    provider = serializers.ChoiceField(
        choices=TechnicianChannel.Provider.choices,
    )
    external_user_id = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
    )
    external_chat_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    external_message_id = serializers.CharField(
        max_length=255,
        trim_whitespace=True,
    )
    text = serializers.CharField(
        max_length=4000,
        trim_whitespace=True,
    )

    def validate_external_user_id(self, value):
        cleaned_value = value.strip()

        if not cleaned_value:
            raise serializers.ValidationError(
                "El identificador del usuario no puede estar vacío."
            )

        return cleaned_value

    def validate_external_message_id(self, value):
        cleaned_value = value.strip()

        if not cleaned_value:
            raise serializers.ValidationError(
                "El identificador del mensaje no puede estar vacío."
            )

        return cleaned_value

    def validate_text(self, value):
        cleaned_text = value.strip()

        if not cleaned_text:
            raise serializers.ValidationError(
                "El mensaje no puede estar vacío."
            )

        return cleaned_text

    def validate(self, data):
        if not data.get("external_chat_id"):
            data["external_chat_id"] = data["external_user_id"]

        return data