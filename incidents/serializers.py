from rest_framework import serializers


class IncomingTextMessageSerializer(serializers.Serializer):
    phone_number = serializers.CharField(
        max_length=20,
    )
    external_message_id = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )
    text = serializers.CharField(
        max_length=4000,
        trim_whitespace=True,
    )

    def validate_phone_number(self, value):
        normalized_number = (
            value.strip()
            .replace("+", "")
            .replace(" ", "")
            .replace("-", "")
        )

        if not normalized_number.isdigit():
            raise serializers.ValidationError(
                "El número solo puede contener dígitos."
            )

        if not 8 <= len(normalized_number) <= 15:
            raise serializers.ValidationError(
                "El número debe contener entre 8 y 15 dígitos."
            )

        return normalized_number

    def validate_text(self, value):
        cleaned_text = value.strip()

        if not cleaned_text:
            raise serializers.ValidationError(
                "El mensaje no puede estar vacío."
            )

        return cleaned_text