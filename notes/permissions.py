from rest_framework import permissions
from .models import NoteCollaborator


class NotePermission(permissions.BasePermission):
    """Permisos personalizados para notas."""
    
    def has_permission(self, request, view):
        """Verificar permisos a nivel de vista."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Verificar permisos a nivel de objeto."""
        
        # Permisos de lectura para usuarios autenticados
        if request.method in permissions.SAFE_METHODS:
            # El autor siempre puede leer
            if obj.author == request.user:
                return True
            
            # Colaboradores activos pueden leer
            if obj.collaborators.filter(
                id=request.user.id,
                notecollaborator__is_active=True
            ).exists():
                return True
            
            # Notas públicas publicadas pueden ser leídas por cualquiera
            if obj.visibility == 'public' and obj.status == 'published':
                return True
            
            return False
        
        # Permisos de escritura
        else:
            # Solo el autor puede eliminar
            if view.action == 'destroy':
                return obj.author == request.user
            
            # El autor siempre puede editar
            if obj.author == request.user:
                return True
            
            # Verificar permisos de colaboradores
            try:
                collaborator = obj.notecollaborator_set.get(
                    user=request.user,
                    is_active=True
                )
                
                # Permisos según el tipo de colaborador
                if view.action in ['update', 'partial_update']:
                    return collaborator.permission in ['edit', 'admin']
                
                if view.action in ['share', 'unshare']:
                    return collaborator.permission == 'admin'
                
                return collaborator.permission in ['edit', 'admin']
                
            except NoteCollaborator.DoesNotExist:
                return False


class CategoryPermission(permissions.BasePermission):
    """Permisos para categorías."""
    
    def has_permission(self, request, view):
        """Verificar permisos a nivel de vista."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Verificar permisos a nivel de objeto."""
        # Solo el creador puede gestionar sus categorías
        return obj.created_by == request.user


class TagPermission(permissions.BasePermission):
    """Permisos para etiquetas."""
    
    def has_permission(self, request, view):
        """Verificar permisos a nivel de vista."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Verificar permisos a nivel de objeto."""
        # Solo el creador puede gestionar sus etiquetas
        return obj.created_by == request.user


class CommentPermission(permissions.BasePermission):
    """Permisos para comentarios."""
    
    def has_permission(self, request, view):
        """Verificar permisos a nivel de vista."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Verificar permisos a nivel de objeto."""
        
        # Verificar que el usuario tenga acceso a la nota
        note = obj.note
        
        # El autor de la nota siempre puede gestionar comentarios
        if note.author == request.user:
            return True
        
        # El autor del comentario puede editar/eliminar su comentario
        if obj.author == request.user:
            return request.method in ['GET', 'PUT', 'PATCH', 'DELETE']
        
        # Colaboradores con permisos de comentario o superior pueden leer
        if request.method in permissions.SAFE_METHODS:
            try:
                collaborator = note.notecollaborator_set.get(
                    user=request.user,
                    is_active=True
                )
                return collaborator.permission in ['comment', 'edit', 'admin']
            except NoteCollaborator.DoesNotExist:
                pass
        
        return False


class AttachmentPermission(permissions.BasePermission):
    """Permisos para archivos adjuntos."""
    
    def has_permission(self, request, view):
        """Verificar permisos a nivel de vista."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Verificar permisos a nivel de objeto."""
        
        # El usuario que subió el archivo puede gestionarlo
        if obj.uploaded_by == request.user:
            return True
        
        # Verificar permisos a través de las notas asociadas
        for note in obj.notes.all():
            # Autor de la nota puede gestionar attachments
            if note.author == request.user:
                return True
            
            # Colaboradores con permisos de edición pueden gestionar
            try:
                collaborator = note.notecollaborator_set.get(
                    user=request.user,
                    is_active=True
                )
                if collaborator.permission in ['edit', 'admin']:
                    return True
            except NoteCollaborator.DoesNotExist:
                continue
        
        return False


class GroupPermission(permissions.BasePermission):
    """Permisos para grupos."""
    
    def has_permission(self, request, view):
        """Verificar permisos a nivel de vista."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Verificar permisos a nivel de objeto."""
        
        # El propietario del grupo tiene todos los permisos
        if obj.owner == request.user:
            return True
        
        # Verificar membresía y permisos
        try:
            from groups.models import GroupMembership
            membership = GroupMembership.objects.get(
                group=obj,
                user=request.user,
                is_active=True
            )
            
            # Permisos de lectura para miembros
            if request.method in permissions.SAFE_METHODS:
                return True
            
            # Permisos de escritura según el rol
            if view.action in ['update', 'partial_update']:
                return membership.role in ['owner', 'admin']
            
            if view.action == 'destroy':
                return membership.role == 'owner'
            
            if view.action in ['invite_member', 'remove_member']:
                return membership.role in ['owner', 'admin', 'moderator']
            
            return membership.role in ['owner', 'admin']
            
        except GroupMembership.DoesNotExist:
            # No es miembro del grupo
            
            # Puede ver grupos públicos
            if (request.method in permissions.SAFE_METHODS and 
                obj.visibility == 'public'):
                return True
            
            return False


class IsOwnerOrReadOnly(permissions.BasePermission):
    """Permiso que solo permite al propietario editar."""
    
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura para todos
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Permisos de escritura solo para el propietario
        return obj.owner == request.user or obj.created_by == request.user


class IsAuthorOrReadOnly(permissions.BasePermission):
    """Permiso que solo permite al autor editar."""
    
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura para todos
        if request.method in permissions.SAFE_METHODS:
            return True
        
        # Permisos de escritura solo para el autor
        return obj.author == request.user


class IsCollaboratorOrReadOnly(permissions.BasePermission):
    """Permiso para colaboradores con diferentes niveles."""
    
    def has_object_permission(self, request, view, obj):
        # Permisos de lectura para usuarios autenticados
        if request.method in permissions.SAFE_METHODS:
            return request.user and request.user.is_authenticated
        
        # Verificar si es colaborador con permisos de escritura
        try:
            collaborator = obj.notecollaborator_set.get(
                user=request.user,
                is_active=True
            )
            return collaborator.permission in ['edit', 'admin']
        except NoteCollaborator.DoesNotExist:
            return False


class AdminOrReadOnly(permissions.BasePermission):
    """Permiso que solo permite a administradores escribir."""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user and request.user.is_staff
