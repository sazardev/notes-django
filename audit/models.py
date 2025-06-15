from django.db import models
from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import uuid
import json


class AuditLog(models.Model):
    """Registro de auditoría para todas las acciones del sistema."""
    
    ACTION_CHOICES = [
        ('create', 'Crear'),
        ('read', 'Leer'),
        ('update', 'Actualizar'),
        ('delete', 'Eliminar'),
        ('share', 'Compartir'),
        ('unshare', 'Dejar de compartir'),
        ('invite', 'Invitar'),
        ('accept', 'Aceptar'),
        ('reject', 'Rechazar'),
        ('login', 'Iniciar sesión'),
        ('logout', 'Cerrar sesión'),
        ('export', 'Exportar'),
        ('import', 'Importar'),
        ('archive', 'Archivar'),
        ('restore', 'Restaurar'),
        ('permission_change', 'Cambio de permisos'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Baja'),
        ('medium', 'Media'),
        ('high', 'Alta'),
        ('critical', 'Crítica'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Usuario que realiza la acción
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    
    # Información de la sesión
    session_key = models.CharField(max_length=40, blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Acción realizada
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)
    app_label = models.CharField(max_length=100)
    
    # Objeto afectado (usando GenericForeignKey)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=50, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Detalles de la acción
    description = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='low')
    
    # Datos antes y después del cambio (para updates)
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    changed_fields = models.JSONField(default=list, blank=True)
    
    # Metadatos adicionales
    metadata = models.JSONField(default=dict, blank=True)
    
    # Request information
    request_method = models.CharField(max_length=10, blank=True)
    request_path = models.CharField(max_length=500, blank=True)
    request_data = models.JSONField(null=True, blank=True)
    
    # Timestamps
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Registro de Auditoría'
        verbose_name_plural = 'Registros de Auditoría'
        db_table = 'audit_log'
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['model_name', 'timestamp']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['ip_address', 'timestamp']),
            models.Index(fields=['severity']),
            models.Index(fields=['timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        user_display = self.user.display_name if self.user else 'Sistema'
        return f"{user_display} - {self.action} {self.model_name} - {self.timestamp}"
    
    @classmethod
    def log_action(cls, user, action, obj, description, request=None, **kwargs):
        """Método helper para crear logs de auditoría."""
        
        # Obtener información del request si está disponible
        ip_address = '127.0.0.1'
        user_agent = ''
        session_key = ''
        request_method = ''
        request_path = ''
        request_data = None
        
        if request:
            ip_address = cls._get_client_ip(request)
            user_agent = request.META.get('HTTP_USER_AGENT', '')
            session_key = request.session.session_key or ''
            request_method = request.method
            request_path = request.path
            
            # Solo capturar datos del request para ciertas acciones
            if action in ['create', 'update'] and hasattr(request, 'data'):
                request_data = dict(request.data)
        
        # Obtener información del objeto
        content_type = None
        object_id = None
        model_name = 'Unknown'
        app_label = 'Unknown'
        
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            object_id = str(obj.pk)
            model_name = obj.__class__.__name__
            app_label = obj._meta.app_label
        
        return cls.objects.create(
            user=user,
            session_key=session_key,
            ip_address=ip_address,
            user_agent=user_agent,
            action=action,
            model_name=model_name,
            app_label=app_label,
            content_type=content_type,
            object_id=object_id,
            description=description,
            request_method=request_method,
            request_path=request_path,
            request_data=request_data,
            **kwargs
        )
    
    @staticmethod
    def _get_client_ip(request):
        """Obtiene la IP real del cliente."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class SecurityEvent(models.Model):
    """Eventos de seguridad específicos."""
    
    EVENT_TYPES = [
        ('login_success', 'Login exitoso'),
        ('login_failed', 'Login fallido'),
        ('password_change', 'Cambio de contraseña'),
        ('password_reset', 'Reset de contraseña'),
        ('account_locked', 'Cuenta bloqueada'),
        ('account_unlocked', 'Cuenta desbloqueada'),
        ('permission_escalation', 'Escalación de permisos'),
        ('suspicious_activity', 'Actividad sospechosa'),
        ('data_export', 'Exportación de datos'),
        ('bulk_delete', 'Eliminación masiva'),
        ('admin_access', 'Acceso administrativo'),
        ('api_abuse', 'Abuso de API'),
    ]
    
    RISK_LEVELS = [
        ('low', 'Bajo'),
        ('medium', 'Medio'),
        ('high', 'Alto'),
        ('critical', 'Crítico'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Usuario relacionado (opcional)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='security_events'
    )
    
    # Tipo de evento
    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    risk_level = models.CharField(max_length=20, choices=RISK_LEVELS, default='low')
    
    # Detalles del evento
    description = models.TextField()
    source_ip = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    # Datos contextuales
    context_data = models.JSONField(default=dict, blank=True)
    
    # Estado del evento
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_security_events'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Evento de Seguridad'
        verbose_name_plural = 'Eventos de Seguridad'
        db_table = 'audit_security_event'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['event_type', 'created_at']),
            models.Index(fields=['risk_level', 'created_at']),
            models.Index(fields=['source_ip', 'created_at']),
            models.Index(fields=['is_resolved']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        user_display = self.user.display_name if self.user else 'Desconocido'
        return f"{self.event_type} - {user_display} - {self.created_at}"
    
    def resolve(self, resolved_by, notes=''):
        """Marca el evento como resuelto."""
        self.is_resolved = True
        self.resolved_by = resolved_by
        self.resolved_at = timezone.now()
        self.resolution_notes = notes
        self.save()


class DataAccess(models.Model):
    """Registro de acceso a datos sensibles."""
    
    ACCESS_TYPES = [
        ('view', 'Visualización'),
        ('download', 'Descarga'),
        ('export', 'Exportación'),
        ('print', 'Impresión'),
        ('share', 'Compartir'),
        ('copy', 'Copiar'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Usuario que accede
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='data_accesses'
    )
    
    # Objeto accedido
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.CharField(max_length=50)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Tipo de acceso
    access_type = models.CharField(max_length=20, choices=ACCESS_TYPES)
    
    # Detalles del acceso
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    
    # Metadatos del acceso
    duration = models.PositiveIntegerField(null=True, blank=True)  # en segundos
    bytes_transferred = models.PositiveBigIntegerField(null=True, blank=True)
    
    # Información adicional
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    accessed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Acceso a Datos'
        verbose_name_plural = 'Accesos a Datos'
        db_table = 'audit_data_access'
        indexes = [
            models.Index(fields=['user', 'accessed_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['access_type', 'accessed_at']),
            models.Index(fields=['ip_address']),
        ]
        ordering = ['-accessed_at']
    
    def __str__(self):
        return f"{self.user.display_name} - {self.access_type} - {self.accessed_at}"


class LoginAttempt(models.Model):
    """Intentos de login para detectar ataques de fuerza bruta."""
    
    STATUS_CHOICES = [
        ('success', 'Exitoso'),
        ('failed', 'Fallido'),
        ('blocked', 'Bloqueado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Usuario (puede ser None si el usuario no existe)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='login_attempts'
    )
    
    # Datos del intento
    username = models.CharField(max_length=255)  # Email o username usado
    status = models.CharField(max_length=20, choices=STATUS_CHOICES)
    failure_reason = models.CharField(max_length=100, blank=True)
    
    # Información de la conexión
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField(blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    # Metadatos adicionales
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    attempted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Intento de Login'
        verbose_name_plural = 'Intentos de Login'
        db_table = 'audit_login_attempt'
        indexes = [
            models.Index(fields=['username', 'attempted_at']),
            models.Index(fields=['ip_address', 'attempted_at']),
            models.Index(fields=['status', 'attempted_at']),
            models.Index(fields=['user', 'attempted_at']),
        ]
        ordering = ['-attempted_at']
    
    def __str__(self):
        return f"{self.username} - {self.status} - {self.ip_address} - {self.attempted_at}"
    
    @classmethod
    def get_failed_attempts(cls, username=None, ip_address=None, minutes=15):
        """Obtiene intentos fallidos recientes."""
        from datetime import timedelta
        
        cutoff_time = timezone.now() - timedelta(minutes=minutes)
        query = cls.objects.filter(
            status='failed',
            attempted_at__gte=cutoff_time
        )
        
        if username:
            query = query.filter(username=username)
        
        if ip_address:
            query = query.filter(ip_address=ip_address)
        
        return query.count()


class PermissionChange(models.Model):
    """Registro de cambios de permisos."""
    
    CHANGE_TYPES = [
        ('granted', 'Otorgado'),
        ('revoked', 'Revocado'),
        ('modified', 'Modificado'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Usuario que recibe el cambio de permisos
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='permission_changes_received'
    )
    
    # Usuario que realiza el cambio
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='permission_changes_made'
    )
    
    # Objeto al que se aplica el permiso
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    object_id = models.CharField(max_length=50, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Detalles del cambio
    change_type = models.CharField(max_length=20, choices=CHANGE_TYPES)
    permission_name = models.CharField(max_length=100)
    old_permission = models.CharField(max_length=100, blank=True)
    new_permission = models.CharField(max_length=100, blank=True)
    
    # Razón del cambio
    reason = models.TextField(blank=True)
    
    # Timestamp
    changed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Cambio de Permisos'
        verbose_name_plural = 'Cambios de Permisos'
        db_table = 'audit_permission_change'
        indexes = [
            models.Index(fields=['target_user', 'changed_at']),
            models.Index(fields=['changed_by', 'changed_at']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['change_type', 'changed_at']),
        ]
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.permission_name} {self.change_type} para {self.target_user.display_name}"


class SystemMetrics(models.Model):
    """Métricas del sistema para análisis de uso."""
    
    METRIC_TYPES = [
        ('user_count', 'Cantidad de usuarios'),
        ('note_count', 'Cantidad de notas'),
        ('group_count', 'Cantidad de grupos'),
        ('active_sessions', 'Sesiones activas'),
        ('api_requests', 'Requests de API'),
        ('storage_usage', 'Uso de almacenamiento'),
        ('bandwidth_usage', 'Uso de ancho de banda'),
        ('database_size', 'Tamaño de base de datos'),
    ]
    
    metric_type = models.CharField(max_length=30, choices=METRIC_TYPES)
    value = models.BigIntegerField()
    unit = models.CharField(max_length=20, blank=True)  # bytes, count, etc.
    
    # Metadatos adicionales
    metadata = models.JSONField(default=dict, blank=True)
    
    # Timestamp
    recorded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Métrica del Sistema'
        verbose_name_plural = 'Métricas del Sistema'
        db_table = 'audit_system_metrics'
        indexes = [
            models.Index(fields=['metric_type', 'recorded_at']),
            models.Index(fields=['recorded_at']),
        ]
        ordering = ['-recorded_at']
    
    def __str__(self):
        return f"{self.metric_type}: {self.value} {self.unit} - {self.recorded_at}"
