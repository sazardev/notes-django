from rest_framework import viewsets, status, permissions, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate, login, logout
from django.db.models import Q
from django.utils import timezone

from .models import User, UserPreferences, UserSession
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    LoginSerializer, PasswordChangeSerializer, UserPreferencesSerializer,
    UserSessionSerializer, UserProfileSerializer, UserSearchSerializer
)


class UserViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar usuarios."""
    
    queryset = User.objects.all()
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        """Seleccionar serializer según la acción."""
        if self.action == 'create':
            return UserCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return UserUpdateSerializer
        elif self.action == 'list':
            return UserSearchSerializer
        return UserSerializer
    
    def get_queryset(self):
        """Filtrar usuarios según permisos."""
        if not self.request.user.is_authenticated:
            return User.objects.none()
        
        # Los usuarios solo pueden ver perfiles públicos y el suyo
        queryset = User.objects.filter(
            Q(profile_public=True) | Q(id=self.request.user.id)
        )
        
        # Búsqueda por nombre o email
        search = self.request.query_params.get('search')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) |
                Q(last_name__icontains=search) |
                Q(username__icontains=search) |
                Q(email__icontains=search)
            )
        
        return queryset
    
    def get_permissions(self):
        """Permisos específicos por acción."""
        if self.action == 'create':
            permission_classes = [permissions.AllowAny]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAuthenticated, IsOwnerOrReadOnly]
        else:
            permission_classes = [permissions.IsAuthenticated]
        
        return [permission() for permission in permission_classes]
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        """Obtener perfil del usuario actual."""
        serializer = UserProfileSerializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['put', 'patch'])
    def update_profile(self, request):
        """Actualizar perfil del usuario actual."""
        serializer = UserUpdateSerializer(
            request.user,
            data=request.data,
            partial=request.method == 'PATCH'
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['post'])
    def change_password(self, request):
        """Cambiar contraseña del usuario actual."""
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Contraseña actualizada correctamente'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Obtener estadísticas del usuario."""
        user = request.user
        
        stats = {
            'notes_count': user.authored_notes.count(),
            'collaborations_count': user.collaborated_notes.filter(
                notecollaborator__is_active=True
            ).count(),
            'groups_count': user.groups.filter(
                groupmembership__is_active=True
            ).count(),
            'login_count': user.login_count,
            'join_date': user.date_joined,
            'last_login': user.last_login,
        }
        
        return Response(stats)


class LoginView(APIView):
    """Vista para login de usuarios."""
    
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Autenticar usuario y generar token."""
        serializer = LoginSerializer(data=request.data)
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            # Crear o obtener token
            token, created = Token.objects.get_or_create(user=user)
            
            # Actualizar último login
            user.last_login = timezone.now()
            user.increment_login_count()
            
            # Crear sesión de usuario
            UserSession.objects.create(
                user=user,
                session_key=request.session.session_key or '',
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', ''),
                device_type=self.detect_device_type(request)
            )
            
            # Serializar datos del usuario
            user_serializer = UserSerializer(user)
            
            return Response({
                'token': token.key,
                'user': user_serializer.data,
                'message': 'Login exitoso'
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def get_client_ip(self, request):
        """Obtener IP del cliente."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    def detect_device_type(self, request):
        """Detectar tipo de dispositivo básico."""
        user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
        
        if 'mobile' in user_agent or 'android' in user_agent or 'iphone' in user_agent:
            return 'mobile'
        elif 'tablet' in user_agent or 'ipad' in user_agent:
            return 'tablet'
        else:
            return 'desktop'


class LogoutView(APIView):
    """Vista para logout de usuarios."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Cerrar sesión del usuario."""
        try:
            # Eliminar token
            token = Token.objects.get(user=request.user)
            token.delete()
            
            # Desactivar sesiones del usuario
            UserSession.objects.filter(
                user=request.user,
                is_active=True
            ).update(is_active=False)
            
            return Response({'message': 'Logout exitoso'})
        
        except Token.DoesNotExist:
            return Response(
                {'error': 'Token no encontrado'},
                status=status.HTTP_400_BAD_REQUEST
            )


class RegisterView(generics.CreateAPIView):
    """Vista para registro de usuarios."""
    
    queryset = User.objects.all()
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        """Crear usuario y generar token automáticamente."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # Crear token automáticamente
        token, created = Token.objects.get_or_create(user=user)
        
        # Crear preferencias por defecto
        UserPreferences.objects.create(user=user)
        
        # Serializar datos del usuario
        user_serializer = UserSerializer(user)
        
        return Response({
            'token': token.key,
            'user': user_serializer.data,
            'message': 'Usuario creado exitosamente'
        }, status=status.HTTP_201_CREATED)


class ChangePasswordView(APIView):
    """Vista para cambiar contraseña."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        """Cambiar contraseña del usuario actual."""
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            
            # Invalidar todas las sesiones excepto la actual
            UserSession.objects.filter(
                user=request.user,
                is_active=True
            ).exclude(
                session_key=request.session.session_key
            ).update(is_active=False)
            
            return Response({'message': 'Contraseña actualizada correctamente'})
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ProfileView(generics.RetrieveUpdateAPIView):
    """Vista para ver y actualizar perfil."""
    
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Retornar el usuario actual."""
        return self.request.user


class UserPreferencesView(generics.RetrieveUpdateAPIView):
    """Vista para gestionar preferencias de usuario."""
    
    serializer_class = UserPreferencesSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_object(self):
        """Obtener o crear preferencias del usuario."""
        preferences, created = UserPreferences.objects.get_or_create(
            user=self.request.user
        )
        return preferences


class UserSessionListView(generics.ListAPIView):
    """Vista para listar sesiones activas del usuario."""
    
    serializer_class = UserSessionSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Obtener sesiones del usuario actual."""
        return UserSession.objects.filter(
            user=self.request.user,
            is_active=True
        ).order_by('-last_activity')


class TerminateSessionView(APIView):
    """Vista para terminar una sesión específica."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request, pk=None):
        """Terminar sesión específica."""
        try:
            session = UserSession.objects.get(
                id=pk,
                user=request.user,
                is_active=True
            )
            session.is_active = False
            session.save()
            
            return Response({'message': 'Sesión terminada'})
        
        except UserSession.DoesNotExist:
            return Response(
                {'error': 'Sesión no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permiso que solo permite al propietario editar."""
    
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura para todos
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Permisos de escritura solo para el propietario
        return obj == request.user
