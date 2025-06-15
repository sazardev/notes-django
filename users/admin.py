from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _
from .models import User, UserPreferences, UserSession


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Administración personalizada para el modelo User."""
    
    list_display = ('email', 'display_name', 'is_active', 'is_staff', 'is_verified', 'date_joined')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'is_verified', 'date_joined')
    search_fields = ('email', 'first_name', 'last_name', 'username')
    ordering = ('-date_joined',)
    filter_horizontal = ('groups', 'user_permissions')
    
    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Información Personal'), {
            'fields': ('first_name', 'last_name', 'username', 'bio', 'avatar', 
                      'phone', 'user_timezone', 'language')
        }),
        (_('Configuraciones'), {
            'fields': ('email_notifications', 'push_notifications', 
                      'note_share_notifications', 'group_notifications')
        }),
        (_('Privacidad'), {
            'fields': ('profile_public', 'allow_friend_requests')
        }),
        (_('Permisos'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'is_verified',
                      'groups', 'user_permissions')
        }),
        (_('Fechas importantes'), {
            'fields': ('last_login', 'date_joined')
        }),
        (_('Estadísticas'), {
            'fields': ('login_count', 'last_ip'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    readonly_fields = ('date_joined', 'last_login', 'login_count', 'last_ip')


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    """Administración para las preferencias de usuario."""
    
    list_display = ('user', 'theme', 'notes_view', 'auto_save_enabled', 'updated_at')
    list_filter = ('theme', 'notes_view', 'auto_save_enabled', 'sidebar_collapsed')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    
    fieldsets = (
        (_('Usuario'), {'fields': ('user',)}),
        (_('Interfaz'), {
            'fields': ('theme', 'sidebar_collapsed', 'notes_view')
        }),
        (_('Editor'), {
            'fields': ('editor_font_size', 'editor_font_family', 
                      'auto_save_enabled', 'auto_save_interval')
        }),
        (_('Búsqueda'), {
            'fields': ('search_suggestions_enabled', 'recent_searches_limit')
        }),
    )


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    """Administración para las sesiones de usuario."""
    
    list_display = ('user', 'device_type', 'ip_address', 'location', 'is_active', 'last_activity')
    list_filter = ('device_type', 'is_active', 'created_at', 'last_activity')
    search_fields = ('user__email', 'ip_address', 'location', 'user_agent')
    readonly_fields = ('id', 'session_key', 'created_at', 'last_activity')
    
    fieldsets = (
        (_('Usuario'), {'fields': ('user',)}),
        (_('Sesión'), {
            'fields': ('session_key', 'is_active', 'created_at', 'last_activity')
        }),
        (_('Dispositivo'), {
            'fields': ('device_type', 'user_agent', 'ip_address', 'location')
        }),
    )
    
    def has_add_permission(self, request):
        return False  # No permitir crear sesiones manualmente
