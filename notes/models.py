from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid
import json


class Category(models.Model):
    """Categorías para organizar las notas."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#007bff')  # Color hexadecimal
    icon = models.CharField(max_length=50, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_categories')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Categoría'
        verbose_name_plural = 'Categorías'
        db_table = 'notes_categories'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['created_by']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def full_path(self):
        """Retorna la ruta completa de la categoría."""
        if self.parent:
            return f"{self.parent.full_path} > {self.name}"
        return self.name


class Tag(models.Model):
    """Etiquetas para clasificar las notas."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    color = models.CharField(max_length=7, default='#6c757d')
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tags')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Etiqueta'
        verbose_name_plural = 'Etiquetas'
        db_table = 'notes_tags'
        indexes = [
            models.Index(fields=['name']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Note(models.Model):
    """Modelo principal para las notas."""
    
    PRIORITY_CHOICES = [
        (1, 'Muy Baja'),
        (2, 'Baja'),
        (3, 'Normal'),
        (4, 'Alta'),
        (5, 'Muy Alta'),
    ]
    
    STATUS_CHOICES = [
        ('draft', 'Borrador'),
        ('published', 'Publicada'),
        ('archived', 'Archivada'),
        ('deleted', 'Eliminada'),
    ]
    
    VISIBILITY_CHOICES = [
        ('private', 'Privada'),
        ('shared', 'Compartida'),
        ('public', 'Pública'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    content = models.TextField()
    content_html = models.TextField(blank=True)  # Contenido renderizado en HTML
    
    # Metadatos
    excerpt = models.TextField(max_length=500, blank=True)  # Resumen automático
    word_count = models.PositiveIntegerField(default=0)
    read_time = models.PositiveIntegerField(default=0)  # En minutos
    
    # Clasificación
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='notes')
    tags = models.ManyToManyField(Tag, blank=True, related_name='notes')
    
    # Estado y visibilidad
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')
    priority = models.PositiveSmallIntegerField(choices=PRIORITY_CHOICES, default=3)
    
    # Flags importantes
    is_pinned = models.BooleanField(default=False)
    is_favorite = models.BooleanField(default=False)
    is_template = models.BooleanField(default=False)
    allow_comments = models.BooleanField(default=True)
    
    # Usuarios
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='authored_notes')
    collaborators = models.ManyToManyField(
        settings.AUTH_USER_MODEL, 
        through='NoteCollaborator', 
        through_fields=('note', 'user'),
        related_name='collaborated_notes',
        blank=True
    )
    
    # Archivos adjuntos
    attachments = models.ManyToManyField('Attachment', blank=True, related_name='notes')
    
    # Ubicación (opcional)
    location_name = models.CharField(max_length=255, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # Estadísticas
    view_count = models.PositiveIntegerField(default=0)
    share_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)
    
    # Configuración personalizada
    custom_fields = models.JSONField(default=dict, blank=True)
    
    class Meta:
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'
        db_table = 'notes_notes'
        indexes = [
            models.Index(fields=['author', 'status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['updated_at']),
            models.Index(fields=['priority']),
            models.Index(fields=['is_pinned']),
            models.Index(fields=['visibility']),
            models.Index(fields=['category']),
            models.Index(fields=['title']),
            # Índices compuestos para consultas frecuentes
            models.Index(fields=['author', 'status', 'visibility']),
            models.Index(fields=['created_at', 'priority']),
        ]
        ordering = ['-is_pinned', '-updated_at']
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        """Override save para actualizar metadatos automáticamente."""
        # Actualizar word_count
        self.word_count = len(self.content.split())
        
        # Calcular tiempo de lectura (aprox 200 palabras por minuto)
        self.read_time = max(1, self.word_count // 200)
        
        # Generar excerpt si no existe
        if not self.excerpt and self.content:
            self.excerpt = self.content[:500] + '...' if len(self.content) > 500 else self.content
        
        # Actualizar published_at
        if self.status == 'published' and not self.published_at:
            self.published_at = timezone.now()
        elif self.status == 'archived' and not self.archived_at:
            self.archived_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_collaborative(self):
        """Retorna True si la nota tiene colaboradores."""
        return self.collaborators.exists()
    
    def increment_view_count(self):
        """Incrementa el contador de vistas."""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class NoteCollaborator(models.Model):
    """Modelo intermedio para colaboradores de notas con permisos específicos."""
    
    PERMISSION_CHOICES = [
        ('view', 'Solo lectura'),
        ('comment', 'Comentar'),
        ('edit', 'Editar'),
        ('admin', 'Administrar'),
    ]
    
    note = models.ForeignKey(Note, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='view')
    
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='sent_note_invitations'
    )
    invited_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['note', 'user']
        verbose_name = 'Colaborador de Nota'
        verbose_name_plural = 'Colaboradores de Nota'
        db_table = 'notes_collaborators'
        indexes = [
            models.Index(fields=['note', 'user']),
            models.Index(fields=['permission']),
        ]
    
    def __str__(self):
        return f"{self.user.email} - {self.note.title} ({self.permission})"


class Attachment(models.Model):
    """Archivos adjuntos para las notas."""
    
    FILE_TYPE_CHOICES = [
        ('image', 'Imagen'),
        ('document', 'Documento'),
        ('audio', 'Audio'),
        ('video', 'Video'),
        ('other', 'Otro'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    file = models.FileField(upload_to='attachments/%Y/%m/%d/')
    original_name = models.CharField(max_length=255)
    file_type = models.CharField(max_length=20, choices=FILE_TYPE_CHOICES, default='other')
    file_size = models.PositiveIntegerField()  # En bytes
    mime_type = models.CharField(max_length=100)
    
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_attachments')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Metadatos específicos para imágenes
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Archivo Adjunto'
        verbose_name_plural = 'Archivos Adjuntos'
        db_table = 'notes_attachments'
        indexes = [
            models.Index(fields=['uploaded_by']),
            models.Index(fields=['file_type']),
            models.Index(fields=['uploaded_at']),
        ]
    
    def __str__(self):
        return self.original_name
    
    @property
    def file_size_human(self):
        """Retorna el tamaño del archivo en formato legible."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if self.file_size < 1024.0:
                return f"{self.file_size:.1f} {unit}"
            self.file_size /= 1024.0
        return f"{self.file_size:.1f} TB"


class NoteVersion(models.Model):
    """Historial de versiones de las notas."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='versions')
    version_number = models.PositiveIntegerField()
    
    # Contenido de la versión
    title = models.CharField(max_length=255)
    content = models.TextField()
    content_html = models.TextField(blank=True)
    
    # Metadatos de la versión
    change_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Estadísticas de cambios
    characters_added = models.IntegerField(default=0)
    characters_removed = models.IntegerField(default=0)
    words_added = models.IntegerField(default=0)
    words_removed = models.IntegerField(default=0)
    
    class Meta:
        unique_together = ['note', 'version_number']
        verbose_name = 'Versión de Nota'
        verbose_name_plural = 'Versiones de Nota'
        db_table = 'notes_versions'
        indexes = [
            models.Index(fields=['note', 'version_number']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['-version_number']
    
    def __str__(self):
        return f"{self.note.title} - v{self.version_number}"


class Comment(models.Model):
    """Comentarios en las notas."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='note_comments')
    
    content = models.TextField()
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # Ubicación del comentario en el texto (opcional)
    text_position = models.PositiveIntegerField(null=True, blank=True)
    selected_text = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_resolved = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Comentario'
        verbose_name_plural = 'Comentarios'
        db_table = 'notes_comments'
        indexes = [
            models.Index(fields=['note', 'created_at']),
            models.Index(fields=['author']),
            models.Index(fields=['parent']),
        ]
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comentario de {self.author.display_name} en {self.note.title}"


class NoteView(models.Model):
    """Registro de visualizaciones de notas para estadísticas."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    note = models.ForeignKey(Note, on_delete=models.CASCADE, related_name='note_views')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    duration = models.PositiveIntegerField(default=0)  # Tiempo en segundos
    
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Visualización de Nota'
        verbose_name_plural = 'Visualizaciones de Nota'
        db_table = 'notes_views'
        indexes = [
            models.Index(fields=['note', 'viewed_at']),
            models.Index(fields=['user', 'viewed_at']),
            models.Index(fields=['ip_address']),
        ]
    
    def __str__(self):
        user_display = self.user.display_name if self.user else f"Anónimo ({self.ip_address})"
        return f"{user_display} vio {self.note.title}"


class SavedSearch(models.Model):
    """Búsquedas guardadas por los usuarios."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_searches')
    
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    query_params = models.JSONField()  # Parámetros de búsqueda serializados
    
    is_notification_enabled = models.BooleanField(default=False)
    notification_frequency = models.CharField(
        max_length=20,
        choices=[
            ('immediate', 'Inmediato'),
            ('daily', 'Diario'),
            ('weekly', 'Semanal'),
        ],
        default='daily'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_executed = models.DateTimeField(null=True, blank=True)
    execution_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ['user', 'name']
        verbose_name = 'Búsqueda Guardada'
        verbose_name_plural = 'Búsquedas Guardadas'
        db_table = 'notes_saved_searches'
        indexes = [
            models.Index(fields=['user', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.user.display_name}"
