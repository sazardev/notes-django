from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
import uuid


class UserManager(BaseUserManager):
    """Manager personalizado para el modelo User."""
    
    def create_user(self, email, password=None, **extra_fields):
        """Crea y guarda un usuario regular."""
        if not email:
            raise ValueError('El email es obligatorio')
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        """Crea y guarda un superusuario."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser debe tener is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser debe tener is_superuser=True.')
        
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Modelo de usuario personalizado."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, verbose_name='Email')
    username = models.CharField(
        max_length=150, 
        unique=True, 
        null=True, 
        blank=True,
        validators=[RegexValidator(
            regex=r'^[\w.@+-]+$',
            message='Username solo puede contener letras, números y @/./+/-/_'
        )]
    )
    first_name = models.CharField(max_length=30, verbose_name='Nombre')
    last_name = models.CharField(max_length=30, verbose_name='Apellido')
    
    # Campos de perfil    bio = models.TextField(max_length=500, blank=True, verbose_name='Biografía')
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    user_timezone = models.CharField(max_length=50, default='UTC')
    language = models.CharField(max_length=10, default='en')
    
    # Configuraciones de notificaciones
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    note_share_notifications = models.BooleanField(default=True)
    group_notifications = models.BooleanField(default=True)
    
    # Configuraciones de privacidad
    profile_public = models.BooleanField(default=False)
    allow_friend_requests = models.BooleanField(default=True)
    
    # Estados del usuario
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    
    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Campos para auditoría
    login_count = models.PositiveIntegerField(default=0)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    
    objects = UserManager()
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    class Meta:
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'
        db_table = 'users_user'
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['username']),
            models.Index(fields=['is_active']),
            models.Index(fields=['date_joined']),
        ]
    
    def __str__(self):
        return self.email
    
    @property
    def full_name(self):
        """Retorna el nombre completo del usuario."""
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def display_name(self):
        """Retorna el nombre a mostrar (username o nombre completo)."""
        return self.username or self.full_name or self.email
    
    def get_avatar_url(self):
        """Retorna la URL del avatar o una imagen por defecto."""
        if self.avatar:
            return self.avatar.url
        return '/static/images/default-avatar.png'
    
    def increment_login_count(self):
        """Incrementa el contador de logins."""
        self.login_count += 1
        self.save(update_fields=['login_count'])


class UserPreferences(models.Model):
    """Preferencias específicas del usuario."""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='preferences')
    
    # Configuraciones de la interfaz
    theme = models.CharField(
        max_length=20, 
        choices=[('light', 'Claro'), ('dark', 'Oscuro'), ('auto', 'Automático')],
        default='auto'
    )
    sidebar_collapsed = models.BooleanField(default=False)
    notes_view = models.CharField(
        max_length=20,
        choices=[('list', 'Lista'), ('grid', 'Cuadrícula'), ('kanban', 'Kanban')],
        default='list'
    )
    
    # Configuraciones de editor
    editor_font_size = models.PositiveSmallIntegerField(default=14)
    editor_font_family = models.CharField(
        max_length=50,
        choices=[
            ('monospace', 'Monospace'),
            ('serif', 'Serif'), 
            ('sans-serif', 'Sans-serif')
        ],
        default='sans-serif'
    )
    auto_save_enabled = models.BooleanField(default=True)
    auto_save_interval = models.PositiveIntegerField(default=30)  # segundos
    
    # Configuraciones de búsqueda
    search_suggestions_enabled = models.BooleanField(default=True)
    recent_searches_limit = models.PositiveSmallIntegerField(default=10)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Preferencias de Usuario'
        verbose_name_plural = 'Preferencias de Usuarios'
        db_table = 'users_preferences'
    
    def __str__(self):
        return f"Preferencias de {self.user.email}"


class UserSession(models.Model):
    """Modelo para rastrear sesiones de usuario."""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=40, unique=True)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    device_type = models.CharField(
        max_length=20,
        choices=[
            ('desktop', 'Escritorio'),
            ('mobile', 'Móvil'),
            ('tablet', 'Tablet'),
            ('unknown', 'Desconocido')
        ],
        default='unknown'
    )
    location = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Sesión de Usuario'
        verbose_name_plural = 'Sesiones de Usuario'
        db_table = 'users_sessions'
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['session_key']),
            models.Index(fields=['last_activity']),
        ]
    
    def __str__(self):
        return f"Sesión de {self.user.email} - {self.ip_address}"
