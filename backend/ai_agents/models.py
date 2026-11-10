"""
Persistence for the agent layer:

* AgentConversation  – chat history per user (raw Claude content blocks)
* AgentToolCall      – audit log of every tool invocation (who / what / result)
* PendingAction      – human-in-the-loop queue: agents *propose* writes,
                       a human approves before anything changes
* SafetyAlert        – prescription safety findings that need acknowledgement
* ClinicalBrief      – cached pre-visit summaries for doctors
* LabInsight         – patient-friendly lab result explanations
* Notification       – in-app messages (reminders, collections, follow-ups)
"""
from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class AgentConversation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='agent_conversations')
    role = models.CharField(max_length=10)  # role of the user when created (selects the agent)
    title = models.CharField(max_length=200, blank=True)
    # Raw Messages-API history (list of {role, content}); replayed unchanged.
    messages = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'Conversation {self.pk} ({self.user})'


class AgentToolCall(models.Model):
    STATUS_CHOICES = (('ok', 'OK'), ('error', 'Error'), ('denied', 'Denied'), ('proposed', 'Proposed'))

    conversation = models.ForeignKey(AgentConversation, on_delete=models.CASCADE, null=True, blank=True,
                                     related_name='tool_calls')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='agent_tool_calls')
    agent = models.CharField(max_length=50)
    tool_name = models.CharField(max_length=100)
    tool_input = models.JSONField(default=dict)
    result_summary = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='ok')
    duration_ms = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'created_at'])]


class PendingAction(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),   # approved and executed successfully
        ('rejected', 'Rejected'),
        ('failed', 'Failed'),       # approved but execution failed
        ('expired', 'Expired'),
    )
    ACTION_TYPES = (
        ('book_appointment', 'Book appointment'),
        ('cancel_appointment', 'Cancel appointment'),
        ('draft_invoice', 'Create invoice'),
        ('send_patient_message', 'Send patient message'),
    )

    conversation = models.ForeignKey(AgentConversation, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='pending_actions')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='requested_actions')
    # Who must approve. Usually the requester; admin-only actions go to admins.
    approver_role = models.CharField(max_length=10, default='self')
    action_type = models.CharField(max_length=40, choices=ACTION_TYPES)
    payload = models.JSONField(default=dict)
    summary = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    result = models.JSONField(default=dict, blank=True)
    decided_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='decided_actions')
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action_type} [{self.status}]'


class SafetyAlert(models.Model):
    SEVERITY_CHOICES = (('info', 'Info'), ('warning', 'Warning'), ('critical', 'Critical'))

    prescription = models.ForeignKey('medical_records.Prescription', on_delete=models.CASCADE,
                                     related_name='safety_alerts')
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    category = models.CharField(max_length=40)  # allergy | interaction | contraindication | dose | duplicate
    message = models.TextField()
    evidence = models.JSONField(default=dict, blank=True)
    acknowledged_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgement_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class ClinicalBrief(models.Model):
    appointment = models.OneToOneField('appointments.Appointment', on_delete=models.CASCADE,
                                       related_name='clinical_brief')
    content = models.TextField()
    highlights = models.JSONField(default=list, blank=True)
    source = models.CharField(max_length=10, default='rules')  # 'llm' | 'rules'
    generated_at = models.DateTimeField(auto_now=True)


class LabInsight(models.Model):
    lab_test = models.OneToOneField('medical_records.LabTest', on_delete=models.CASCADE, related_name='insight')
    patient_explanation = models.TextField()
    abnormal_flags = models.JSONField(default=list, blank=True)
    needs_doctor_review = models.BooleanField(default=False)
    source = models.CharField(max_length=10, default='rules')
    generated_at = models.DateTimeField(auto_now=True)


class Notification(models.Model):
    KIND_CHOICES = (
        ('appointment_reminder', 'Appointment reminder'),
        ('payment_reminder', 'Payment reminder'),
        ('care_followup', 'Care follow-up'),
        ('lab_result', 'Lab result'),
        ('safety_alert', 'Safety alert'),
        ('agent', 'Assistant message'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=30, choices=KIND_CHOICES)
    title = models.CharField(max_length=200)
    body = models.TextField()
    link = models.CharField(max_length=200, blank=True)
    # Prevents the periodic agents from sending the same message twice
    dedupe_key = models.CharField(max_length=120, unique=True, null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
