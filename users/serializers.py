from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from .models import User, UserPreferences, UserSession


class UserSerializer(serializers.ModelSerializer):
    """Serializer para el modelo User."""
    
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.ReadOnlyField(source='get_avatar_url')
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'display_name', 'bio', 'avatar', 'avatar_url',
            'phone', 'timezone', 'language', 'profile_public',
            'email_notifications', 'push_notifications',
            'note_share_notifications', 'group_notifications',
            'is_verified', 'date_joined', 'last_login'
        ]
        read_only_fields = [
            'id', 'is_verified', 'date_joined', 'last_login',
            'full_name', 'display_name', 'avatar_url'
        ]


class UserCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear nuevos usuarios."""
    
    password = serializers.CharField(write_only=True, validators=[validate_password])
    password_confirm = serializers.CharField(write_only=True)
    
    class Meta:
        model = User
        fields = [
            'email', 'username', 'first_name', 'last_name',
            'password', 'password_confirm', 'timezone', 'language'
        ]
    
    def validate(self, attrs):
        """Validar que las contraseñas coincidan."""
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError("Las contraseñas no coinciden.")
        return attrs
    
    def create(self, validated_data):
        """Crear usuario con contraseña encriptada."""
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer para actualizar usuarios."""
    
    class Meta:
        model = User
        fields = [
            'username', 'first_name', 'last_name', 'bio', 'avatar',
            'phone', 'timezone', 'language', 'profile_public',
            'email_notifications', 'push_notifications',
            'note_share_notifications', 'group_notifications'
        ]


class PasswordChangeSerializer(serializers.Serializer):
    """Serializer para cambio de contraseña."""
    
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, validators=[validate_password])
    new_password_confirm = serializers.CharField(required=True)
    
    def validate_old_password(self, value):
        """Validar contraseña actual."""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("La contraseña actual es incorrecta.")
        return value
    
    def validate(self, attrs):
        """Validar que las nuevas contraseñas coincidan."""
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError("Las nuevas contraseñas no coinciden.")
        return attrs
    
    def save(self):
        """Cambiar contraseña."""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer para login."""
    
    email = serializers.EmailField(required=True)
    password = serializers.CharField(required=True)
    
    def validate(self, attrs):
        """Validar credenciales."""
        email = attrs.get('email')
        password = attrs.get('password')
        
        if email and password:
            user = authenticate(email=email, password=password)
            if not user:
                raise serializers.ValidationError("Credenciales inválidas.")
            if not user.is_active:
                raise serializers.ValidationError("Usuario inactivo.")
            attrs['user'] = user
        else:
            raise serializers.ValidationError("Email y contraseña son requeridos.")
        
        return attrs


class UserPreferencesSerializer(serializers.ModelSerializer):
    """Serializer para preferencias de usuario."""
    
    class Meta:
        model = UserPreferences
        fields = [
            'theme', 'sidebar_collapsed', 'notes_view',
            'editor_font_size', 'editor_font_family',
            'auto_save_enabled', 'auto_save_interval',
            'search_suggestions_enabled', 'recent_searches_limit'
        ]


class UserSessionSerializer(serializers.ModelSerializer):
    """Serializer para sesiones de usuario."""
    
    class Meta:
        model = UserSession
        fields = [
            'id', 'session_key', 'ip_address', 'device_type',
            'location', 'is_active', 'created_at', 'last_activity'
        ]
        read_only_fields = ['id', 'session_key', 'created_at']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer completo del perfil de usuario."""
    
    preferences = UserPreferencesSerializer(read_only=True)
    active_sessions = UserSessionSerializer(
        source='sessions',
        many=True,
        read_only=True
    )
    full_name = serializers.ReadOnlyField()
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.ReadOnlyField(source='get_avatar_url')
    
    # Estadísticas
    notes_count = serializers.SerializerMethodField()
    groups_count = serializers.SerializerMethodField()
    collaborations_count = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'full_name', 'display_name', 'bio', 'avatar', 'avatar_url',
            'phone', 'timezone', 'language', 'profile_public',
            'email_notifications', 'push_notifications',
            'note_share_notifications', 'group_notifications',
            'is_verified', 'date_joined', 'last_login', 'login_count',
            'preferences', 'active_sessions',
            'notes_count', 'groups_count', 'collaborations_count'
        ]
        read_only_fields = [
            'id', 'is_verified', 'date_joined', 'last_login', 'login_count',
            'full_name', 'display_name', 'avatar_url', 'preferences',
            'active_sessions', 'notes_count', 'groups_count', 'collaborations_count'
        ]
    
    def get_notes_count(self, obj):
        """Obtener cantidad de notas del usuario."""
        return obj.authored_notes.filter(status__in=['draft', 'published']).count()
    
    def get_groups_count(self, obj):
        """Obtener cantidad de grupos del usuario."""
        return obj.groups.filter(groupmembership__is_active=True).count()
    
    def get_collaborations_count(self, obj):
        """Obtener cantidad de colaboraciones activas."""
        return obj.collaborated_notes.filter(
            notecollaborator__is_active=True
        ).count()


class UserSearchSerializer(serializers.ModelSerializer):
    """Serializer para búsqueda de usuarios."""
    
    display_name = serializers.ReadOnlyField()
    avatar_url = serializers.ReadOnlyField(source='get_avatar_url')
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'username', 'first_name', 'last_name',
            'display_name', 'bio', 'avatar_url', 'is_verified'
        ]


class UserInviteSerializer(serializers.Serializer):
    """Serializer para invitar usuarios."""
    
    email = serializers.EmailField(required=True)
    message = serializers.CharField(max_length=500, required=False)
    
    def validate_email(self, value):
        """Validar que el email no esté registrado."""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "Ya existe un usuario con este email."
            )
        return value
