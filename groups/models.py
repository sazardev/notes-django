from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class Group(models.Model):
    """Grupos para organizar usuarios y compartir notas."""
    
    VISIBILITY_CHOICES = [
        ('private', 'Privado'),
        ('invite_only', 'Solo por invitación'),
        ('public', 'Público'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='groups/avatars/', null=True, blank=True)
    
    # Configuración del grupo
    visibility = models.CharField(max_length=20, choices=VISIBILITY_CHOICES, default='private')
    is_active = models.BooleanField(default=True)
    max_members = models.PositiveIntegerField(default=100)
    
    # Permisos por defecto para nuevos miembros
    default_member_permission = models.CharField(
        max_length=20,
        choices=[
            ('view', 'Solo lectura'),
            ('comment', 'Comentar'),
            ('edit', 'Editar'),
            ('admin', 'Administrar'),
        ],
        default='view'
    )
    
    # Configuraciones
    allow_member_invites = models.BooleanField(default=True)
    allow_public_notes = models.BooleanField(default=False)
    require_approval = models.BooleanField(default=True)
      # Usuarios
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='owned_groups'
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through='GroupMembership',
        through_fields=('group', 'user'),
        related_name='user_groups',
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Estadísticas
    member_count = models.PositiveIntegerField(default=0)
    note_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = 'Grupo'
        verbose_name_plural = 'Grupos'
        db_table = 'groups_group'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['owner']),
            models.Index(fields=['visibility']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Override para actualizar estadísticas."""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        if is_new:
            # Crear membresía para el owner
            GroupMembership.objects.create(
                group=self,
                user=self.owner,
                role='owner',
                permission='admin',
                is_active=True
            )
    
    def update_member_count(self):
        """Actualiza el contador de miembros."""
        self.member_count = self.members.filter(
            groupmembership__is_active=True
        ).count()
        self.save(update_fields=['member_count'])
    
    def get_avatar_url(self):
        """Retorna la URL del avatar o una imagen por defecto."""
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-group-avatar.png'


class GroupMembership(models.Model):
    """Membresía de usuarios en grupos."""
    
    ROLE_CHOICES = [
        ('owner', 'Propietario'),
        ('admin', 'Administrador'), 
        ('moderator', 'Moderador'),
        ('member', 'Miembro'),
    ]
    
    PERMISSION_CHOICES = [
        ('view', 'Solo lectura'),
        ('comment', 'Comentar'),
        ('edit', 'Editar'),
        ('admin', 'Administrar'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('active', 'Activo'),
        ('suspended', 'Suspendido'),
        ('banned', 'Bloqueado'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='view')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Invitación
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sent_group_invitations'
    )
    invitation_message = models.TextField(blank=True)
    
    # Timestamps
    invited_at = models.DateTimeField(auto_now_add=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    last_activity = models.DateTimeField(null=True, blank=True)
    
    # Estado
    is_active = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['group', 'user']
        verbose_name = 'Membresía de Grupo'
        verbose_name_plural = 'Membresías de Grupo'
        db_table = 'groups_membership'
        indexes = [
            models.Index(fields=['group', 'user']),
            models.Index(fields=['role']),
            models.Index(fields=['status']),
            models.Index(fields=['is_active']),
        ]
    
    def __str__(self):
        return f"{self.user.display_name} - {self.group.name} ({self.role})"
    
    def accept_invitation(self):
        """Acepta la invitación al grupo."""
        self.status = 'active'
        self.is_active = True
        self.joined_at = timezone.now()
        self.save()
        
        # Actualizar contador del grupo
        self.group.update_member_count()
    
    def can_invite_members(self):
        """Verifica si el usuario puede invitar miembros."""
        return (
            self.is_active and 
            self.role in ['owner', 'admin', 'moderator'] and
            self.group.allow_member_invites
        )
    
    def can_manage_notes(self):
        """Verifica si el usuario puede gestionar notas del grupo."""
        return (
            self.is_active and 
            self.permission in ['edit', 'admin']
        )


class GroupInvitation(models.Model):
    """Invitaciones a grupos."""
    
    STATUS_CHOICES = [
        ('pending', 'Pendiente'),
        ('accepted', 'Aceptada'),
        ('declined', 'Rechazada'),
        ('expired', 'Expirada'),
        ('cancelled', 'Cancelada'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invitations')
    
    # Puede ser invitación por email o por usuario existente
    invited_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='received_group_invitations'
    )
    invited_email = models.EmailField(blank=True)
    
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_group_invitations_detailed'
    )
    
    message = models.TextField(blank=True)
    role = models.CharField(max_length=20, choices=GroupMembership.ROLE_CHOICES, default='member')
    permission = models.CharField(max_length=20, choices=GroupMembership.PERMISSION_CHOICES, default='view')
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    
    # Configuración
    token = models.CharField(max_length=64, unique=True)
    
    class Meta:
        verbose_name = 'Invitación a Grupo'
        verbose_name_plural = 'Invitaciones a Grupo'
        db_table = 'groups_invitations'
        indexes = [
            models.Index(fields=['group', 'status']),
            models.Index(fields=['invited_user']),
            models.Index(fields=['invited_email']),
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        invitee = self.invited_user.display_name if self.invited_user else self.invited_email
        return f"Invitación a {invitee} para {self.group.name}"
    
    def is_expired(self):
        """Verifica si la invitación ha expirado."""
        return timezone.now() > self.expires_at
    
    def accept(self, user=None):
        """Acepta la invitación."""
        if self.is_expired():
            raise ValueError("La invitación ha expirado")
        
        if self.status != 'pending':
            raise ValueError("La invitación ya fue procesada")
        
        # Si la invitación es por email, asignar el usuario
        if not self.invited_user and user:
            self.invited_user = user
        
        # Crear o actualizar la membresía
        membership, created = GroupMembership.objects.get_or_create(
            group=self.group,
            user=self.invited_user,
            defaults={
                'role': self.role,
                'permission': self.permission,
                'invited_by': self.invited_by,
                'status': 'active',
                'is_active': True,
                'joined_at': timezone.now(),
            }
        )
        
        if not created:
            membership.status = 'active'
            membership.is_active = True
            membership.joined_at = timezone.now()
            membership.save()
        
        # Actualizar invitación
        self.status = 'accepted'
        self.responded_at = timezone.now()
        self.save()
        
        # Actualizar contador del grupo
        self.group.update_member_count()
        
        return membership


class GroupNote(models.Model):
    """Relación entre grupos y notas."""
    
    PERMISSION_CHOICES = [
        ('view', 'Solo lectura'),
        ('comment', 'Comentar'),
        ('edit', 'Editar'),
    ]
    
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='group_notes')
    note = models.ForeignKey('notes.Note', on_delete=models.CASCADE, related_name='shared_groups')
    
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='shared_group_notes'
    )
    
    permission = models.CharField(max_length=20, choices=PERMISSION_CHOICES, default='view')
    
    # Configuración
    is_pinned = models.BooleanField(default=False)
    is_featured = models.BooleanField(default=False)
    
    # Timestamps
    shared_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['group', 'note']
        verbose_name = 'Nota de Grupo'
        verbose_name_plural = 'Notas de Grupo'
        db_table = 'groups_notes'
        indexes = [
            models.Index(fields=['group', 'shared_at']),
            models.Index(fields=['note']),
            models.Index(fields=['shared_by']),
        ]
    
    def __str__(self):
        return f"{self.note.title} en {self.group.name}"


class GroupSettings(models.Model):
    """Configuraciones específicas del grupo."""
    
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='settings')
    
    # Configuraciones de notificaciones
    notify_new_members = models.BooleanField(default=True)
    notify_new_notes = models.BooleanField(default=True)
    notify_note_updates = models.BooleanField(default=False)
    notify_comments = models.BooleanField(default=True)
    
    # Configuraciones de contenido
    allow_file_uploads = models.BooleanField(default=True)
    max_file_size = models.PositiveIntegerField(default=10485760)  # 10MB en bytes
    allowed_file_types = models.JSONField(
        default=list,
        help_text="Lista de tipos de archivo permitidos"
    )
    
    # Configuraciones de moderación
    auto_approve_notes = models.BooleanField(default=True)
    require_approval_for_edits = models.BooleanField(default=False)
    
    # Configuraciones de búsqueda
    enable_full_text_search = models.BooleanField(default=True)
    index_note_content = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Configuración de Grupo'
        verbose_name_plural = 'Configuraciones de Grupo'
        db_table = 'groups_settings'
    
    def __str__(self):
        return f"Configuración de {self.group.name}"
