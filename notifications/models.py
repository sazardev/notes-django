from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import uuid
import json


class NotificationType(models.Model):
    """Tipos de notificaciones disponibles."""
    
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    
    # Configuración del tipo
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=50, blank=True)
    color = models.CharField(max_length=7, default='#007bff')
    
    # Plantillas para diferentes canales
    email_template = models.CharField(max_length=100, blank=True)
    push_template = models.CharField(max_length=100, blank=True)
    web_template = models.CharField(max_length=100, blank=True)
    
    # Configuración por defecto
    default_email_enabled = models.BooleanField(default=True)
    default_push_enabled = models.BooleanField(default=True)
    default_web_enabled = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Tipo de Notificación'
        verbose_name_plural = 'Tipos de Notificación'
        db_table = 'notifications_type'
        ordering = ['display_name']
    
    def __str__(self):
        return self.display_name


class Notification(models.Model):
    """Notificaciones del sistema."""
    
    PRIORITY_CHOICES = [
        ('low', 'Baja'),
        ('normal', 'Normal'),
        ('high', 'Alta'),
        ('urgent', 'Urgente'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('sent', 'Enviada'),
        ('delivered', 'Entregada'),
        ('read', 'Leída'),
        ('failed', 'Fallida'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Receptor
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Emisor (opcional, puede ser el sistema)
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_notifications'
    )
    
    # Tipo y contenido
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Objeto relacionado (genérico)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=50, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Configuración
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Datos adicionales
    data = models.JSONField(default=dict, blank=True)
    
    # Canales de entrega
    send_email = models.BooleanField(default=False)
    send_push = models.BooleanField(default=False)
    send_web = models.BooleanField(default=True)
    
    # URLs de acción (opcional)
    action_url = models.URLField(blank=True)
    action_text = models.CharField(max_length=50, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    # Agrupación (para evitar spam)
    group_key = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        db_table = 'notifications_notification'
        indexes = [
            models.Index(fields=['recipient', 'status']),
            models.Index(fields=['notification_type']),
            models.Index(fields=['created_at']),
            models.Index(fields=['scheduled_at']),
            models.Index(fields=['priority']),
            models.Index(fields=['group_key']),
            models.Index(fields=['content_type', 'object_id']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.title} para {self.recipient.display_name}"
    
    def mark_as_read(self):
        """Marca la notificación como leída."""
        if not self.read_at:
            self.read_at = timezone.now()
            self.status = 'read'
            self.save(update_fields=['read_at', 'status'])
    
    def mark_as_sent(self):
        """Marca la notificación como enviada."""
        self.sent_at = timezone.now()
        self.status = 'sent'
        self.save(update_fields=['sent_at', 'status'])
    
    def mark_as_delivered(self):
        """Marca la notificación como entregada."""
        self.delivered_at = timezone.now()
        self.status = 'delivered'
        self.save(update_fields=['delivered_at', 'status'])
    
    def is_expired(self):
        """Verifica si la notificación ha expirado."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at
    
    @property
    def is_read(self):
        """Verifica si la notificación fue leída."""
        return self.read_at is not None


class NotificationPreference(models.Model):
    """Preferencias de notificación por usuario y tipo."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preferences'
    )
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='user_preferences'
    )
    
    # Canales habilitados
    email_enabled = models.BooleanField(default=True)
    push_enabled = models.BooleanField(default=True)
    web_enabled = models.BooleanField(default=True)
    
    # Configuración de frecuencia
    frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Inmediato'),
            ('daily', 'Diario'),
            ('weekly', 'Semanal'),
            ('disabled', 'Deshabilitado'),
        ],
        default='immediate'
    )
    
    # Horario preferido para notificaciones (formato JSON)
    preferred_time = models.JSONField(
        default=dict,
        help_text="Horario preferido para recibir notificaciones"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'notification_type']
        verbose_name = 'Preferencia de Notificación'
        verbose_name_plural = 'Preferencias de Notificación'
        db_table = 'notifications_preference'
        indexes = [
            models.Index(fields=['user', 'notification_type']),
        ]
    
    def __str__(self):
        return f"{self.user.display_name} - {self.notification_type.display_name}"


class NotificationDelivery(models.Model):
    """Registro de entregas de notificaciones."""
    
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('push', 'Push'),
        ('web', 'Web'),
        ('sms', 'SMS'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('processing', 'Procesando'),
        ('sent', 'Enviada'),
        ('delivered', 'Entregada'),
        ('failed', 'Fallida'),
        ('bounced', 'Rebotada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='deliveries'
    )
    
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Detalles del canal
    recipient_address = models.CharField(max_length=255)  # email, phone, etc.
    provider = models.CharField(max_length=50, blank=True)  # SendGrid, FCM, etc.
    external_id = models.CharField(max_length=100, blank=True)  # ID del proveedor
    
    # Respuesta del proveedor
    response_data = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    
    # Métricas
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    
    class Meta:
        verbose_name = 'Entrega de Notificación'
        verbose_name_plural = 'Entregas de Notificación'
        db_table = 'notifications_delivery'
        indexes = [
            models.Index(fields=['notification', 'channel']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['channel', 'status']),
        ]
    
    def __str__(self):
        return f"{self.notification.title} via {self.channel} - {self.status}"
    
    def mark_as_sent(self):
        """Marca como enviada."""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])
    
    def mark_as_delivered(self):
        """Marca como entregada."""
        self.status = 'delivered'
        self.delivered_at = timezone.now()
        self.save(update_fields=['status', 'delivered_at'])
    
    def mark_as_failed(self, error_message=''):
        """Marca como fallida."""
        self.status = 'failed'
        self.failed_at = timezone.now()
        self.error_message = error_message
        self.save(update_fields=['status', 'failed_at', 'error_message'])
    
    def can_retry(self):
        """Verifica si se puede reintentar el envío."""
        return self.retry_count < self.max_retries and self.status == 'failed'


class NotificationTemplate(models.Model):
    """Plantillas para notificaciones."""
    
    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('push', 'Push'),
        ('web', 'Web'),
        ('sms', 'SMS'),
    ]
    
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='templates'
    )
    
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    language = models.CharField(max_length=10, default='en')
    
    # Contenido de la plantilla
    subject = models.CharField(max_length=255, blank=True)  # Para email
    title = models.CharField(max_length=255, blank=True)    # Para push/web
    body = models.TextField()
    
    # Variables disponibles (formato JSON)
    available_variables = models.JSONField(
        default=list,
        help_text="Lista de variables disponibles en la plantilla"
    )
    
    # Configuración
    is_active = models.BooleanField(default=True)
    is_default = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['notification_type', 'channel', 'language']
        verbose_name = 'Plantilla de Notificación'
        verbose_name_plural = 'Plantillas de Notificación'
        db_table = 'notifications_template'
        indexes = [
            models.Index(fields=['notification_type', 'channel']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.notification_type.display_name} - {self.channel} ({self.language})"
    
    def render(self, context):
        """Renderiza la plantilla con el contexto dado."""
        from django.template import Template, Context
        
        # Renderizar subject (si existe)
        subject = ''
        if self.subject:
            subject_template = Template(self.subject)
            subject = subject_template.render(Context(context))
        
        # Renderizar title (si existe)
        title = ''
        if self.title:
            title_template = Template(self.title)
            title = title_template.render(Context(context))
        
        # Renderizar body
        body_template = Template(self.body)
        body = body_template.render(Context(context))
        
        return {
            'subject': subject,
            'title': title,
            'body': body,
        }


class NotificationGroup(models.Model):
    """Agrupación de notificaciones para evitar spam."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_groups'
    )
    
    notification_type = models.ForeignKey(
        NotificationType,
        on_delete=models.CASCADE,
        related_name='groups'
    )
    
    group_key = models.CharField(max_length=100)
    
    # Configuración de agrupación
    interval_minutes = models.PositiveIntegerField(default=60)
    max_notifications = models.PositiveIntegerField(default=10)
    
    # Estado
    last_sent_at = models.DateTimeField(null=True, blank=True)
    notification_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'notification_type', 'group_key']
        verbose_name = 'Grupo de Notificación'
        verbose_name_plural = 'Grupos de Notificación'
        db_table = 'notifications_group'
        indexes = [
            models.Index(fields=['user', 'group_key']),
            models.Index(fields=['last_sent_at']),
        ]
    
    def __str__(self):
        return f"{self.user.display_name} - {self.group_key}"
    
    def should_send_notification(self):
        """Determina si se debe enviar una notificación agrupada."""
        if not self.last_sent_at:
            return True
        
        time_diff = timezone.now() - self.last_sent_at
        time_passed = time_diff.total_seconds() / 60  # en minutos
        
        return (
            time_passed >= self.interval_minutes or
            self.notification_count >= self.max_notifications
        )
    
    def reset_counter(self):
        """Reinicia el contador de notificaciones."""
        self.notification_count = 0
        self.last_sent_at = timezone.now()
        self.save(update_fields=['notification_count', 'last_sent_at'])


class WebSocketConnection(models.Model):
    """Conexiones WebSocket activas para notificaciones en tiempo real."""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='websocket_connections'
    )
    
    connection_id = models.CharField(max_length=100, unique=True)
    channel_name = models.CharField(max_length=100)
    
    # Información de la conexión
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Estado
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Conexión WebSocket'
        verbose_name_plural = 'Conexiones WebSocket'
        db_table = 'notifications_websocket'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['connection_id']),
            models.Index(fields=['last_seen']),
        ]
    
    def __str__(self):
        return f"{self.user.display_name} - {self.connection_id}"
