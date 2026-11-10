from rest_framework import serializers

from .models import (AgentConversation, AgentToolCall, ClinicalBrief, LabInsight, Notification,
                     PendingAction, SafetyAlert)


def display_messages(raw):
    """Turn stored Messages-API history into simple chat bubbles for the UI."""
    out = []
    for m in raw:
        content = m.get('content')
        blocks = [{'type': 'text', 'text': content}] if isinstance(content, str) else (content or [])
        texts = [b.get('text', '') for b in blocks if b.get('type') == 'text']
        if m['role'] == 'user':
            # Strip the injected "[Context — ...]" line
            texts = [t.split(']\n', 1)[1] if t.startswith('[Context') and ']\n' in t else t for t in texts]
        text = '\n'.join(t for t in texts if t).strip()
        if text:
            out.append({'role': m['role'], 'text': text})
    return out


class ConversationSerializer(serializers.ModelSerializer):
    messages = serializers.SerializerMethodField()

    class Meta:
        model = AgentConversation
        fields = ['id', 'title', 'role', 'created_at', 'updated_at', 'messages']

    def get_messages(self, obj):
        return display_messages(obj.messages)


class ConversationListSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentConversation
        fields = ['id', 'title', 'role', 'created_at', 'updated_at']


class PendingActionSerializer(serializers.ModelSerializer):
    requested_by_name = serializers.CharField(source='requested_by.get_full_name', read_only=True)

    class Meta:
        model = PendingAction
        fields = ['id', 'conversation', 'action_type', 'summary', 'payload', 'status', 'approver_role',
                  'result', 'requested_by', 'requested_by_name', 'decided_at', 'created_at']


class SafetyAlertSerializer(serializers.ModelSerializer):
    medication_name = serializers.CharField(source='prescription.medication_name', read_only=True)
    patient_name = serializers.CharField(source='prescription.medical_record.patient.get_full_name', read_only=True)

    class Meta:
        model = SafetyAlert
        fields = ['id', 'prescription', 'medication_name', 'patient_name', 'severity', 'category', 'message',
                  'evidence', 'acknowledged_by', 'acknowledged_at', 'acknowledgement_note', 'created_at']


class ClinicalBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClinicalBrief
        fields = ['appointment', 'content', 'highlights', 'source', 'generated_at']


class LabInsightSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabInsight
        fields = ['lab_test', 'patient_explanation', 'abnormal_flags', 'needs_doctor_review', 'source', 'generated_at']


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'kind', 'title', 'body', 'link', 'read_at', 'created_at']


class ToolCallSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True, default=None)

    class Meta:
        model = AgentToolCall
        fields = ['id', 'conversation', 'username', 'agent', 'tool_name', 'tool_input', 'result_summary',
                  'status', 'duration_ms', 'created_at']


class ChatRequestSerializer(serializers.Serializer):
    message = serializers.CharField(max_length=4000, trim_whitespace=True)
    conversation_id = serializers.IntegerField(required=False, allow_null=True)


class PrescriptionCheckSerializer(serializers.Serializer):
    patient = serializers.IntegerField()
    medication_name = serializers.CharField(max_length=200)
    dosage = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
    frequency = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')
