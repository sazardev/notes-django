from rest_framework import serializers
from django.db import transaction
from .models import (
    Note, Category, Tag, NoteCollaborator, Attachment,
    NoteVersion, Comment, NoteView, SavedSearch
)
from users.serializers import UserSearchSerializer


class CategorySerializer(serializers.ModelSerializer):
    """Serializer para categorías."""
    
    full_path = serializers.ReadOnlyField()
    notes_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'color', 'icon',
            'parent', 'full_path', 'notes_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at', 'updated_at']
    
    def get_notes_count(self, obj):
        """Obtener cantidad de notas en la categoría."""
        return obj.notes.filter(status__in=['draft', 'published']).count()


class TagSerializer(serializers.ModelSerializer):
    """Serializer para etiquetas."""
    
    notes_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tag
        fields = [
            'id', 'name', 'description', 'color',
            'notes_count', 'created_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_at']
    
    def get_notes_count(self, obj):
        """Obtener cantidad de notas con esta etiqueta."""
        return obj.notes.filter(status__in=['draft', 'published']).count()


class AttachmentSerializer(serializers.ModelSerializer):
    """Serializer para archivos adjuntos."""
    
    file_size_human = serializers.ReadOnlyField()
    
    class Meta:
        model = Attachment
        fields = [
            'id', 'file', 'original_name', 'file_type',
            'file_size', 'file_size_human', 'mime_type',
            'image_width', 'image_height', 'uploaded_at'
        ]
        read_only_fields = [
            'id', 'uploaded_by', 'file_size', 'mime_type',
            'image_width', 'image_height', 'uploaded_at'
        ]


class NoteCollaboratorSerializer(serializers.ModelSerializer):
    """Serializer para colaboradores de notas."""
    
    user = UserSearchSerializer(read_only=True)
    invited_by = UserSearchSerializer(read_only=True)
    
    class Meta:
        model = NoteCollaborator
        fields = [
            'user', 'permission', 'invited_by',
            'invited_at', 'accepted_at', 'is_active'
        ]
        read_only_fields = [
            'invited_by', 'invited_at', 'accepted_at'
        ]


class CommentSerializer(serializers.ModelSerializer):
    """Serializer para comentarios."""
    
    author = UserSearchSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'content', 'author', 'parent',
            'text_position', 'selected_text',
            'created_at', 'updated_at', 'is_resolved',
            'replies'
        ]
        read_only_fields = ['id', 'author', 'created_at', 'updated_at']
    
    def get_replies(self, obj):
        """Obtener respuestas al comentario."""
        if obj.replies.exists():
            return CommentSerializer(obj.replies.all(), many=True).data
        return []


class NoteVersionSerializer(serializers.ModelSerializer):
    """Serializer para versiones de notas."""
    
    created_by = UserSearchSerializer(read_only=True)
    
    class Meta:
        model = NoteVersion
        fields = [
            'id', 'version_number', 'title', 'content',
            'content_html', 'change_summary', 'created_by',
            'created_at', 'characters_added', 'characters_removed',
            'words_added', 'words_removed'
        ]
        read_only_fields = [
            'id', 'version_number', 'created_by', 'created_at',
            'characters_added', 'characters_removed',
            'words_added', 'words_removed'
        ]


class NoteSerializer(serializers.ModelSerializer):
    """Serializer básico para notas."""
    
    author = UserSearchSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    is_collaborative = serializers.ReadOnlyField()
    
    # IDs para asignación
    category_id = serializers.UUIDField(write_only=True, required=False, allow_null=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'content', 'content_html', 'excerpt',
            'word_count', 'read_time', 'category', 'category_id',
            'tags', 'tag_ids', 'status', 'visibility', 'priority',
            'is_pinned', 'is_favorite', 'is_template',
            'allow_comments', 'author', 'location_name',
            'latitude', 'longitude', 'created_at', 'updated_at',
            'published_at', 'view_count', 'share_count',
            'comment_count', 'custom_fields', 'is_collaborative'
        ]
        read_only_fields = [
            'id', 'author', 'word_count', 'read_time', 'excerpt',
            'created_at', 'updated_at', 'published_at',
            'view_count', 'share_count', 'comment_count',
            'is_collaborative'
        ]
    
    def create(self, validated_data):
        """Crear nota con relaciones."""
        category_id = validated_data.pop('category_id', None)
        tag_ids = validated_data.pop('tag_ids', [])
        
        # Crear la nota
        note = Note.objects.create(**validated_data)
        
        # Asignar categoría
        if category_id:
            try:
                category = Category.objects.get(id=category_id)
                note.category = category
                note.save()
            except Category.DoesNotExist:
                pass
        
        # Asignar etiquetas
        if tag_ids:
            tags = Tag.objects.filter(id__in=tag_ids)
            note.tags.set(tags)
        
        return note
    
    def update(self, instance, validated_data):
        """Actualizar nota con relaciones."""
        category_id = validated_data.pop('category_id', None)
        tag_ids = validated_data.pop('tag_ids', None)
        
        # Actualizar campos básicos
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Actualizar categoría
        if category_id is not None:
            if category_id:
                try:
                    category = Category.objects.get(id=category_id)
                    instance.category = category
                    instance.save()
                except Category.DoesNotExist:
                    pass
            else:
                instance.category = None
                instance.save()
        
        # Actualizar etiquetas
        if tag_ids is not None:
            tags = Tag.objects.filter(id__in=tag_ids)
            instance.tags.set(tags)
        
        return instance


class NoteDetailSerializer(NoteSerializer):
    """Serializer detallado para notas."""
    
    collaborators = NoteCollaboratorSerializer(
        source='notecollaborator_set',
        many=True,
        read_only=True
    )
    attachments = AttachmentSerializer(many=True, read_only=True)
    comments = CommentSerializer(
        many=True,
        read_only=True
    )
    versions = NoteVersionSerializer(
        many=True,
        read_only=True
    )
    
    # Permisos del usuario actual
    user_permission = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_comment = serializers.SerializerMethodField()
    
    class Meta(NoteSerializer.Meta):
        fields = NoteSerializer.Meta.fields + [
            'collaborators', 'attachments', 'comments',
            'versions', 'user_permission', 'can_edit', 'can_comment'
        ]
    
    def get_user_permission(self, obj):
        """Obtener permisos del usuario actual sobre la nota."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        
        user = request.user
        
        # Si es el autor, tiene todos los permisos
        if obj.author == user:
            return 'admin'
        
        # Verificar colaboración
        try:
            collaborator = obj.notecollaborator_set.get(
                user=user,
                is_active=True
            )
            return collaborator.permission
        except NoteCollaborator.DoesNotExist:
            pass
        
        # Verificar acceso a través de grupos
        # TODO: Implementar lógica de grupos
        
        return None
    
    def get_can_edit(self, obj):
        """Verificar si el usuario puede editar la nota."""
        permission = self.get_user_permission(obj)
        return permission in ['admin', 'edit']
    
    def get_can_comment(self, obj):
        """Verificar si el usuario puede comentar la nota."""
        permission = self.get_user_permission(obj)
        return permission in ['admin', 'edit', 'comment'] and obj.allow_comments


class NoteCreateSerializer(serializers.ModelSerializer):
    """Serializer para crear notas."""
    
    category_id = serializers.UUIDField(required=False, allow_null=True)
    tag_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    
    class Meta:
        model = Note
        fields = [
            'title', 'content', 'category_id', 'tag_ids',
            'status', 'visibility', 'priority',
            'is_pinned', 'is_favorite', 'is_template',
            'allow_comments', 'location_name',
            'latitude', 'longitude', 'custom_fields'
        ]
    
    def create(self, validated_data):
        """Crear nota con autor automático."""
        category_id = validated_data.pop('category_id', None)
        tag_ids = validated_data.pop('tag_ids', [])
        
        # Asignar autor automáticamente
        request = self.context['request']
        validated_data['author'] = request.user
        
        # Crear la nota
        note = Note.objects.create(**validated_data)
        
        # Asignar categoría
        if category_id:
            try:
                category = Category.objects.get(
                    id=category_id,
                    created_by=request.user
                )
                note.category = category
                note.save()
            except Category.DoesNotExist:
                pass
        
        # Asignar etiquetas
        if tag_ids:
            tags = Tag.objects.filter(
                id__in=tag_ids,
                created_by=request.user
            )
            note.tags.set(tags)
        
        return note


class NoteListSerializer(serializers.ModelSerializer):
    """Serializer optimizado para listado de notas."""
    
    author = UserSearchSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    collaborators_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Note
        fields = [
            'id', 'title', 'excerpt', 'word_count', 'read_time',
            'category', 'tags', 'status', 'visibility', 'priority',
            'is_pinned', 'is_favorite', 'author', 'created_at',
            'updated_at', 'view_count', 'comment_count',
            'collaborators_count'
        ]
    
    def get_collaborators_count(self, obj):
        """Obtener cantidad de colaboradores."""
        return obj.collaborators.filter(
            notecollaborator__is_active=True
        ).count()


class SavedSearchSerializer(serializers.ModelSerializer):
    """Serializer para búsquedas guardadas."""
    
    class Meta:
        model = SavedSearch
        fields = [
            'id', 'name', 'description', 'query_params',
            'is_notification_enabled', 'notification_frequency',
            'created_at', 'last_executed', 'execution_count'
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'last_executed', 'execution_count'
        ]


class NoteShareSerializer(serializers.Serializer):
    """Serializer para compartir notas."""
    
    user_ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True
    )
    emails = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_empty=True
    )
    permission = serializers.ChoiceField(
        choices=NoteCollaborator.PERMISSION_CHOICES,
        default='view'
    )
    message = serializers.CharField(max_length=500, required=False)
    
    def validate(self, attrs):
        """Validar que se proporcionen usuarios o emails."""
        user_ids = attrs.get('user_ids', [])
        emails = attrs.get('emails', [])
        
        if not user_ids and not emails:
            raise serializers.ValidationError(
                "Debe proporcionar al menos un usuario o email."
            )
        
        return attrs


class NoteExportSerializer(serializers.Serializer):
    """Serializer para exportar notas."""
    
    FORMAT_CHOICES = [
        ('markdown', 'Markdown'),
        ('html', 'HTML'),
        ('pdf', 'PDF'),
        ('json', 'JSON'),
    ]
    
    format = serializers.ChoiceField(choices=FORMAT_CHOICES, default='markdown')
    include_attachments = serializers.BooleanField(default=True)
    include_comments = serializers.BooleanField(default=False)
    include_versions = serializers.BooleanField(default=False)


class NoteStatsSerializer(serializers.Serializer):
    """Serializer para estadísticas de notas."""
    
    total_notes = serializers.IntegerField()
    published_notes = serializers.IntegerField()
    draft_notes = serializers.IntegerField()
    archived_notes = serializers.IntegerField()
    total_words = serializers.IntegerField()
    total_views = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    categories_count = serializers.IntegerField()
    tags_count = serializers.IntegerField()
    collaborations_count = serializers.IntegerField()
