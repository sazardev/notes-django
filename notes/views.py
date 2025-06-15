from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q, Count, Prefetch
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import (
    Note, Category, Tag, NoteCollaborator, Attachment,
    NoteVersion, Comment, NoteView, SavedSearch
)
from .serializers import (
    NoteSerializer, NoteDetailSerializer, NoteCreateSerializer,
    NoteListSerializer, CategorySerializer, TagSerializer,
    NoteCollaboratorSerializer, AttachmentSerializer,
    NoteVersionSerializer, CommentSerializer, SavedSearchSerializer,
    NoteShareSerializer, NoteExportSerializer, NoteStatsSerializer
)
from .filters import NoteFilter, CategoryFilter, TagFilter
from .permissions import NotePermission, CategoryPermission, TagPermission
from audit.models import AuditLog


class NotePagination(PageNumberPagination):
    """Paginación personalizada para notas."""
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


class NoteViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar notas con funcionalidades avanzadas."""
    
    pagination_class = NotePagination
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = NoteFilter
    search_fields = ['title', 'content', 'tags__name', 'category__name']
    ordering_fields = [
        'title', 'created_at', 'updated_at', 'priority', 
        'view_count', 'comment_count', 'word_count'
    ]
    ordering = ['-is_pinned', '-updated_at']
    permission_classes = [permissions.IsAuthenticated, NotePermission]
    
    def get_queryset(self):
        """Obtener queryset optimizado según el usuario."""
        user = self.request.user
        
        if not user.is_authenticated:
            return Note.objects.none()
        
        # Queryset base con prefetch optimizado
        queryset = Note.objects.select_related(
            'author', 'category'
        ).prefetch_related(
            'tags',
            'collaborators',
            Prefetch(
                'notecollaborator_set',
                queryset=NoteCollaborator.objects.select_related('user')
            )
        )
        
        # Filtrar según visibilidad y permisos
        user_notes = Q(author=user)
        shared_notes = Q(
            collaborators=user,
            notecollaborator__is_active=True
        )
        public_notes = Q(visibility='public', status='published')
        
        queryset = queryset.filter(
            user_notes | shared_notes | public_notes
        ).distinct()
        
        return queryset
    
    def get_serializer_class(self):
        """Seleccionar serializer según la acción."""
        if self.action == 'create':
            return NoteCreateSerializer
        elif self.action == 'list':
            return NoteListSerializer
        elif self.action in ['retrieve', 'update', 'partial_update']:
            return NoteDetailSerializer
        return NoteSerializer
    
    def perform_create(self, serializer):
        """Crear nota asignando el autor."""
        note = serializer.save(author=self.request.user)
        
        # Crear log de auditoría
        AuditLog.log_action(
            user=self.request.user,
            action='create',
            obj=note,
            description=f'Nota creada: {note.title}',
            request=self.request
        )
    
    def perform_update(self, serializer):
        """Actualizar nota con tracking."""
        # Guardar referencia para el signal
        serializer.instance._updated_by = self.request.user
        note = serializer.save()
        
        # El signal se encarga del log de auditoría
    
    def perform_destroy(self, instance):
        """Eliminar nota con tracking."""
        # Guardar referencia para el signal
        instance._deleted_by = self.request.user
        
        # Crear log antes de eliminar
        AuditLog.log_action(
            user=self.request.user,
            action='delete',
            obj=instance,
            description=f'Nota eliminada: {instance.title}',
            request=self.request
        )
        
        instance.delete()
    
    @action(detail=True, methods=['post'])
    def share(self, request, pk=None):
        """Compartir nota con otros usuarios."""
        note = self.get_object()
        serializer = NoteShareSerializer(data=request.data)
        
        if serializer.is_valid():
            user_ids = serializer.validated_data.get('user_ids', [])
            emails = serializer.validated_data.get('emails', [])
            permission = serializer.validated_data['permission']
            message = serializer.validated_data.get('message', '')
            
            shared_count = 0
            
            # Compartir con usuarios existentes
            from users.models import User
            for user_id in user_ids:
                try:
                    user = User.objects.get(id=user_id)
                    collaborator, created = NoteCollaborator.objects.get_or_create(
                        note=note,
                        user=user,
                        defaults={
                            'permission': permission,
                            'invited_by': request.user,
                            'is_active': True
                        }
                    )
                    if created:
                        shared_count += 1
                except User.DoesNotExist:
                    continue
            
            # TODO: Enviar invitaciones por email
            
            # Incrementar contador de compartidas
            note.share_count += shared_count
            note.save(update_fields=['share_count'])
            
            return Response({
                'message': f'Nota compartida con {shared_count} usuarios',
                'shared_count': shared_count
            })
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def unshare(self, request, pk=None):
        """Dejar de compartir nota con un usuario."""
        note = self.get_object()
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'user_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            collaborator = NoteCollaborator.objects.get(
                note=note,
                user_id=user_id
            )
            collaborator.delete()
            
            return Response({'message': 'Colaborador eliminado'})
        except NoteCollaborator.DoesNotExist:
            return Response(
                {'error': 'Colaborador no encontrado'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Obtener historial de versiones."""
        note = self.get_object()
        versions = note.versions.all()
        serializer = NoteVersionSerializer(versions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def restore_version(self, request, pk=None):
        """Restaurar una versión específica."""
        note = self.get_object()
        version_id = request.data.get('version_id')
        
        if not version_id:
            return Response(
                {'error': 'version_id es requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            version = note.versions.get(id=version_id)
            
            # Crear nueva versión antes de restaurar
            note._updated_by = request.user
            
            # Restaurar contenido
            note.title = version.title
            note.content = version.content
            note.content_html = version.content_html
            note.save()
            
            return Response({
                'message': f'Versión {version.version_number} restaurada'
            })
        except NoteVersion.DoesNotExist:
            return Response(
                {'error': 'Versión no encontrada'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def toggle_pin(self, request, pk=None):
        """Alternar estado de fijado."""
        note = self.get_object()
        note.is_pinned = not note.is_pinned
        note.save(update_fields=['is_pinned'])
        
        action_text = 'fijada' if note.is_pinned else 'desfijada'
        return Response({'message': f'Nota {action_text}'})
    
    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request, pk=None):
        """Alternar estado de favorito."""
        note = self.get_object()
        note.is_favorite = not note.is_favorite
        note.save(update_fields=['is_favorite'])
        
        action_text = 'marcada como favorita' if note.is_favorite else 'desmarcada como favorita'
        return Response({'message': f'Nota {action_text}'})
    
    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Archivar nota."""
        note = self.get_object()
        note.status = 'archived'
        note.save(update_fields=['status'])
        
        return Response({'message': 'Nota archivada'})
    
    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Publicar nota."""
        note = self.get_object()
        note.status = 'published'
        note.save(update_fields=['status'])
        
        return Response({'message': 'Nota publicada'})
    
    @action(detail=True, methods=['post'])
    def view(self, request, pk=None):
        """Registrar visualización de nota."""
        note = self.get_object()
        
        # Solo registrar si no es el autor
        if note.author != request.user:
            NoteView.objects.create(
                note=note,
                user=request.user if request.user.is_authenticated else None,
                ip_address=self.get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
        
        return Response({'message': 'Visualización registrada'})
    
    @action(detail=True, methods=['post'])
    def export(self, request, pk=None):
        """Exportar nota en diferentes formatos."""
        note = self.get_object()
        serializer = NoteExportSerializer(data=request.data)
        
        if serializer.is_valid():
            format_type = serializer.validated_data['format']
            
            # TODO: Implementar exportación según formato
            # Por ahora solo retornamos la data
            
            data = {
                'title': note.title,
                'content': note.content,
                'format': format_type,
                'exported_at': note.updated_at.isoformat()
            }
            
            return Response(data)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Obtener estadísticas del usuario."""
        user = request.user
        
        stats = {
            'total_notes': user.authored_notes.count(),
            'published_notes': user.authored_notes.filter(status='published').count(),
            'draft_notes': user.authored_notes.filter(status='draft').count(),
            'archived_notes': user.authored_notes.filter(status='archived').count(),
            'total_words': sum(note.word_count for note in user.authored_notes.all()),
            'total_views': sum(note.view_count for note in user.authored_notes.all()),
            'total_comments': sum(note.comment_count for note in user.authored_notes.all()),
            'categories_count': user.created_categories.count(),
            'tags_count': user.created_tags.count(),
            'collaborations_count': user.collaborated_notes.filter(
                notecollaborator__is_active=True
            ).count()
        }
        
        serializer = NoteStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def recent(self, request):
        """Obtener notas recientes."""
        queryset = self.get_queryset().order_by('-updated_at')[:10]
        serializer = NoteListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def favorites(self, request):
        """Obtener notas favoritas."""
        queryset = self.get_queryset().filter(is_favorite=True)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = NoteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = NoteListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def shared(self, request):
        """Obtener notas compartidas conmigo."""
        user = request.user
        queryset = Note.objects.filter(
            collaborators=user,
            notecollaborator__is_active=True
        ).distinct()
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = NoteListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = NoteListSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def get_client_ip(self, request):
        """Obtener IP del cliente."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar categorías."""
    
    serializer_class = CategorySerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = CategoryFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    permission_classes = [permissions.IsAuthenticated, CategoryPermission]
    
    def get_queryset(self):
        """Obtener categorías del usuario."""
        if not self.request.user.is_authenticated:
            return Category.objects.none()
        
        return Category.objects.filter(
            created_by=self.request.user
        ).prefetch_related('children')
    
    def perform_create(self, serializer):
        """Crear categoría asignando el creador."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def notes(self, request, pk=None):
        """Obtener notas de la categoría."""
        category = self.get_object()
        notes = category.notes.filter(
            Q(author=request.user) |
            Q(collaborators=request.user, notecollaborator__is_active=True)
        ).distinct()
        
        serializer = NoteListSerializer(notes, many=True)
        return Response(serializer.data)


class TagViewSet(viewsets.ModelViewSet):
    """ViewSet para gestionar etiquetas."""
    
    serializer_class = TagSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = TagFilter
    search_fields = ['name', 'description']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']
    permission_classes = [permissions.IsAuthenticated, TagPermission]
    
    def get_queryset(self):
        """Obtener etiquetas del usuario."""
        if not self.request.user.is_authenticated:
            return Tag.objects.none()
        
        return Tag.objects.filter(created_by=self.request.user)
    
    def perform_create(self, serializer):
        """Crear etiqueta asignando el creador."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def notes(self, request, pk=None):
        """Obtener notas con esta etiqueta."""
        tag = self.get_object()
        notes = tag.notes.filter(
            Q(author=request.user) |
            Q(collaborators=request.user, notecollaborator__is_active=True)
        ).distinct()
        
        serializer = NoteListSerializer(notes, many=True)
        return Response(serializer.data)
