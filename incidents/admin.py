from django.contrib import admin

from .models import Incident, IncidentDraft, Technician, WhatsAppMessage


@admin.register(Technician)
class TechnicianAdmin(admin.ModelAdmin):
    list_display = (
        "full_name",
        "whatsapp_number",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    search_fields = ("full_name", "whatsapp_number")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("full_name",)


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        "incident_code",
        "technician",
        "unit",
        "equipment",
        "priority",
        "status",
        "created_at",
    )
    list_filter = (
        "priority",
        "status",
        "created_at",
    )
    search_fields = (
        "unit",
        "equipment",
        "failure_type",
        "description",
        "technician__full_name",
        "technician__whatsapp_number",
    )
    readonly_fields = (
        "incident_code",
        "created_at",
        "updated_at",
        "resolved_at",
    )

    @admin.display(description="Código")
    def incident_code(self, obj):
        return obj.code


@admin.register(WhatsAppMessage)
class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "phone_number",
        "direction",
        "message_type",
        "status",
        "technician",
        "incident",
    )
    list_filter = (
        "direction",
        "message_type",
        "status",
        "created_at",
    )
    search_fields = (
        "external_message_id",
        "phone_number",
        "content",
        "technician__full_name",
    )
    readonly_fields = (
        "created_at",
        "processed_at",
    )


@admin.register(IncidentDraft)
class IncidentDraftAdmin(admin.ModelAdmin):
    list_display = (
        "technician",
        "status",
        "incident",
        "updated_at",
        "expires_at",
    )
    list_filter = (
        "status",
        "updated_at",
    )
    search_fields = (
        "technician__full_name",
        "technician__whatsapp_number",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "completed_at",
    )