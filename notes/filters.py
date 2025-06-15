import django_filters
from django.db.models import Q, Count, Avg
from django_filters import rest_framework as filters
from .models import Note, Category, Tag


class NoteFilter(filters.FilterSet):
    """Filtros avanzados para notas."""
    
    # Filtros básicos
    title = filters.CharFilter(field_name='title', lookup_expr='icontains')
    content = filters.CharFilter(field_name='content', lookup_expr='icontains')
    status = filters.ChoiceFilter(choices=Note.STATUS_CHOICES)
    visibility = filters.ChoiceFilter(choices=Note.VISIBILITY_CHOICES)
    priority = filters.RangeFilter()
    
    # Filtros por autor
    author = filters.UUIDFilter(field_name='author__id')
    author_username = filters.CharFilter(
        field_name='author__username', 
        lookup_expr='icontains'
    )
    author_email = filters.CharFilter(
        field_name='author__email', 
        lookup_expr='icontains'
    )
    
    # Filtros por categoría
    category = filters.ModelChoiceFilter(queryset=Category.objects.all())
    category_name = filters.CharFilter(
        field_name='category__name', 
        lookup_expr='icontains'
    )
    no_category = filters.BooleanFilter(
        field_name='category',
        lookup_expr='isnull'
    )
    
    # Filtros por etiquetas
    tags = filters.ModelMultipleChoiceFilter(queryset=Tag.objects.all())
    tag_names = filters.CharFilter(method='filter_tag_names')
    has_tags = filters.BooleanFilter(method='filter_has_tags')
    
    # Filtros booleanos
    is_pinned = filters.BooleanFilter()
    is_favorite = filters.BooleanFilter()
    is_template = filters.BooleanFilter()
    allow_comments = filters.BooleanFilter()
    
    # Filtros por fechas
    created_after = filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='gte'
    )
    created_before = filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='lte'
    )
    updated_after = filters.DateTimeFilter(
        field_name='updated_at', 
        lookup_expr='gte'
    )
    updated_before = filters.DateTimeFilter(
        field_name='updated_at', 
        lookup_expr='lte'
    )
    published_after = filters.DateTimeFilter(
        field_name='published_at', 
        lookup_expr='gte'
    )
    published_before = filters.DateTimeFilter(
        field_name='published_at', 
        lookup_expr='lte'
    )
    
    # Filtros por rango de fechas
    date_range = filters.DateFromToRangeFilter(field_name='created_at')
    updated_range = filters.DateFromToRangeFilter(field_name='updated_at')
    
    # Filtros por métricas
    word_count_min = filters.NumberFilter(
        field_name='word_count', 
        lookup_expr='gte'
    )
    word_count_max = filters.NumberFilter(
        field_name='word_count', 
        lookup_expr='lte'
    )
    read_time_min = filters.NumberFilter(
        field_name='read_time', 
        lookup_expr='gte'
    )
    read_time_max = filters.NumberFilter(
        field_name='read_time', 
        lookup_expr='lte'
    )
    view_count_min = filters.NumberFilter(
        field_name='view_count', 
        lookup_expr='gte'
    )
    view_count_max = filters.NumberFilter(
        field_name='view_count', 
        lookup_expr='lte'
    )
    
    # Filtros por colaboración
    has_collaborators = filters.BooleanFilter(method='filter_has_collaborators')
    collaborator = filters.UUIDFilter(method='filter_collaborator')
    shared_with_me = filters.BooleanFilter(method='filter_shared_with_me')
    
    # Filtros por ubicación
    has_location = filters.BooleanFilter(method='filter_has_location')
    location = filters.CharFilter(
        field_name='location_name', 
        lookup_expr='icontains'
    )
    
    # Filtros por attachments
    has_attachments = filters.BooleanFilter(method='filter_has_attachments')
    attachment_type = filters.CharFilter(method='filter_attachment_type')
    
    # Búsqueda general
    search = filters.CharFilter(method='filter_search')
    
    # Filtros complejos
    modified_by_others = filters.BooleanFilter(method='filter_modified_by_others')
    recently_viewed = filters.BooleanFilter(method='filter_recently_viewed')
    trending = filters.BooleanFilter(method='filter_trending')
    
    class Meta:
        model = Note
        fields = []
    
    def filter_tag_names(self, queryset, name, value):
        """Filtrar por nombres de etiquetas (separados por coma)."""
        if not value:
            return queryset
        
        tag_names = [name.strip() for name in value.split(',')]
        return queryset.filter(tags__name__in=tag_names).distinct()
    
    def filter_has_tags(self, queryset, name, value):
        """Filtrar notas que tienen o no tienen etiquetas."""
        if value is True:
            return queryset.filter(tags__isnull=False).distinct()
        elif value is False:
            return queryset.filter(tags__isnull=True)
        return queryset
    
    def filter_has_collaborators(self, queryset, name, value):
        """Filtrar notas que tienen o no tienen colaboradores."""
        if value is True:
            return queryset.filter(collaborators__isnull=False).distinct()
        elif value is False:
            return queryset.filter(collaborators__isnull=True)
        return queryset
    
    def filter_collaborator(self, queryset, name, value):
        """Filtrar notas donde un usuario específico es colaborador."""
        if not value:
            return queryset
        return queryset.filter(
            collaborators__id=value,
            notecollaborator__is_active=True
        ).distinct()
    
    def filter_shared_with_me(self, queryset, name, value):
        """Filtrar notas compartidas con el usuario actual."""
        if not value or not self.request.user.is_authenticated:
            return queryset
        
        user = self.request.user
        return queryset.filter(
            collaborators=user,
            notecollaborator__is_active=True
        ).distinct()
    
    def filter_has_location(self, queryset, name, value):
        """Filtrar notas que tienen o no tienen ubicación."""
        if value is True:
            return queryset.filter(
                Q(latitude__isnull=False) & Q(longitude__isnull=False)
            )
        elif value is False:
            return queryset.filter(
                Q(latitude__isnull=True) | Q(longitude__isnull=True)
            )
        return queryset
    
    def filter_has_attachments(self, queryset, name, value):
        """Filtrar notas que tienen o no tienen archivos adjuntos."""
        if value is True:
            return queryset.filter(attachments__isnull=False).distinct()
        elif value is False:
            return queryset.filter(attachments__isnull=True)
        return queryset
    
    def filter_attachment_type(self, queryset, name, value):
        """Filtrar por tipo de archivo adjunto."""
        if not value:
            return queryset
        return queryset.filter(attachments__file_type=value).distinct()
    
    def filter_search(self, queryset, name, value):
        """Búsqueda general en título, contenido y etiquetas."""
        if not value:
            return queryset
        
        return queryset.filter(
            Q(title__icontains=value) |
            Q(content__icontains=value) |
            Q(tags__name__icontains=value) |
            Q(category__name__icontains=value)
        ).distinct()
    
    def filter_modified_by_others(self, queryset, name, value):
        """Filtrar notas modificadas por otros usuarios."""
        if not value or not self.request.user.is_authenticated:
            return queryset
        
        user = self.request.user
        return queryset.filter(
            versions__created_by__ne=user
        ).distinct()
    
    def filter_recently_viewed(self, queryset, name, value):
        """Filtrar notas vistas recientemente por el usuario."""
        if not value or not self.request.user.is_authenticated:
            return queryset
        
        from datetime import timedelta
        from django.utils import timezone
        
        user = self.request.user
        recent_time = timezone.now() - timedelta(days=7)
        
        return queryset.filter(
            note_views__user=user,
            note_views__viewed_at__gte=recent_time
        ).distinct()
    
    def filter_trending(self, queryset, name, value):
        """Filtrar notas populares/trending."""
        if not value:
            return queryset
        
        from datetime import timedelta
        from django.utils import timezone
        
        recent_time = timezone.now() - timedelta(days=7)
        
        return queryset.filter(
            note_views__viewed_at__gte=recent_time
        ).annotate(
            recent_views=Count('note_views')
        ).filter(
            recent_views__gte=5
        ).order_by('-recent_views')


class CategoryFilter(filters.FilterSet):
    """Filtros para categorías."""
    
    name = filters.CharFilter(lookup_expr='icontains')
    description = filters.CharFilter(lookup_expr='icontains')
    color = filters.CharFilter()
    parent = filters.ModelChoiceFilter(queryset=Category.objects.all())
    has_parent = filters.BooleanFilter(
        field_name='parent',
        lookup_expr='isnull',
        exclude=True
    )
    created_by = filters.UUIDFilter(field_name='created_by__id')
    
    # Filtros por fechas
    created_after = filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='gte'
    )
    created_before = filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='lte'
    )
    
    # Filtros por métricas
    min_notes = filters.NumberFilter(method='filter_min_notes')
    
    class Meta:
        model = Category
        fields = []
    
    def filter_min_notes(self, queryset, name, value):
        """Filtrar categorías con un mínimo de notas."""
        if not value:
            return queryset
        
        return queryset.annotate(
            notes_count=Count('notes')
        ).filter(notes_count__gte=value)


class TagFilter(filters.FilterSet):
    """Filtros para etiquetas."""
    
    name = filters.CharFilter(lookup_expr='icontains')
    description = filters.CharFilter(lookup_expr='icontains')
    color = filters.CharFilter()
    created_by = filters.UUIDFilter(field_name='created_by__id')
    
    # Filtros por fechas
    created_after = filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='gte'
    )
    created_before = filters.DateTimeFilter(
        field_name='created_at', 
        lookup_expr='lte'
    )
    
    # Filtros por métricas
    min_notes = filters.NumberFilter(method='filter_min_notes')
    popular = filters.BooleanFilter(method='filter_popular')
    
    class Meta:
        model = Tag
        fields = []
    
    def filter_min_notes(self, queryset, name, value):
        """Filtrar etiquetas con un mínimo de notas."""
        if not value:
            return queryset
        
        return queryset.annotate(
            notes_count=Count('notes')
        ).filter(notes_count__gte=value)
    
    def filter_popular(self, queryset, name, value):
        """Filtrar etiquetas populares."""
        if not value:
            return queryset
        
        return queryset.annotate(
            notes_count=Count('notes')
        ).filter(notes_count__gte=10).order_by('-notes_count')
