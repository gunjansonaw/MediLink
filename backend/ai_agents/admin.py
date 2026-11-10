from django.contrib import admin

from .models import (AgentConversation, AgentToolCall, ClinicalBrief, LabInsight, Notification,
                     PendingAction, SafetyAlert)


@admin.register(AgentToolCall)
class AgentToolCallAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'agent', 'tool_name', 'user', 'status', 'duration_ms']
    list_filter = ['agent', 'status', 'tool_name']
    readonly_fields = [f.name for f in AgentToolCall._meta.fields]


@admin.register(PendingAction)
class PendingActionAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'action_type', 'requested_by', 'status', 'approver_role']
    list_filter = ['status', 'action_type']


@admin.register(SafetyAlert)
class SafetyAlertAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'prescription', 'severity', 'category', 'acknowledged_at']
    list_filter = ['severity', 'category']


admin.site.register(AgentConversation)
admin.site.register(ClinicalBrief)
admin.site.register(LabInsight)
admin.site.register(Notification)
