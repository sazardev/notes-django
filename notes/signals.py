from django.db.models.signals import post_save, post_delete, pre_save, m2m_changed
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import difflib

from .models import Note, NoteVersion, Comment, NoteCollaborator, NoteView
from notifications.models import Notification, NotificationType
from audit.models import AuditLog


@receiver(pre_save, sender=Note)
def note_pre_save(sender, instance, **kwargs):
    """Signal antes de guardar una nota."""
    if instance.pk:  # Es una actualización
        try:
            old_instance = Note.objects.get(pk=instance.pk)
            instance._old_instance = old_instance
        except Note.DoesNotExist:
            pass


@receiver(post_save, sender=Note)
def note_post_save(sender, instance, created, **kwargs):
    """Signal después de guardar una nota."""
    
    if created:
        # Nota creada
        handle_note_created(instance)
    else:
        # Nota actualizada
        handle_note_updated(instance)


def handle_note_created(note):
    """Manejar creación de nota."""
    
    # Crear log de auditoría
    AuditLog.objects.create(
        user=note.author,
        action='create',
        model_name='Note',
        app_label='notes',
        content_type=ContentType.objects.get_for_model(note),
        object_id=str(note.pk),
        description=f'Nota creada: {note.title}',
        new_values={
            'title': note.title,
            'status': note.status,
            'visibility': note.visibility,
        }
    )
    
    # Crear primera versión
    create_note_version(note, note.author, 'Versión inicial')
    
    # Notificar por WebSocket
    notify_note_event(note, 'note_created', {
        'note_id': str(note.id),
        'title': note.title,
        'author': note.author.display_name
    })


def handle_note_updated(note):
    """Manejar actualización de nota."""
    
    if not hasattr(note, '_old_instance'):
        return
    
    old_note = note._old_instance
    
    # Detectar cambios
    changed_fields = []
    old_values = {}
    new_values = {}
    
    for field in ['title', 'content', 'status', 'visibility', 'priority']:
        old_value = getattr(old_note, field)
        new_value = getattr(note, field)
        
        if old_value != new_value:
            changed_fields.append(field)
            old_values[field] = old_value
            new_values[field] = new_value
    
    if changed_fields:
        # Crear log de auditoría
        AuditLog.objects.create(
            user=getattr(note, '_updated_by', None),
            action='update',
            model_name='Note',
            app_label='notes',
            content_type=ContentType.objects.get_for_model(note),
            object_id=str(note.pk),
            description=f'Nota actualizada: {note.title}',
            old_values=old_values,
            new_values=new_values,
            changed_fields=changed_fields
        )
        
        # Crear nueva versión si el contenido cambió
        if 'content' in changed_fields or 'title' in changed_fields:
            create_note_version(
                note, 
                getattr(note, '_updated_by', note.author),
                f'Actualización: {", ".join(changed_fields)}'
            )
        
        # Notificar a colaboradores
        notify_note_collaborators(note, 'note_updated', {
            'note_id': str(note.id),
            'title': note.title,
            'changed_fields': changed_fields,
            'updated_by': getattr(note, '_updated_by', note.author).display_name
        })


def create_note_version(note, user, change_summary):
    """Crear una nueva versión de la nota."""
    
    # Obtener el número de versión siguiente
    last_version = note.versions.first()
    version_number = (last_version.version_number + 1) if last_version else 1
    
    # Calcular estadísticas de cambios
    characters_added = 0
    characters_removed = 0
    words_added = 0
    words_removed = 0
    
    if last_version:
        old_content = last_version.content
        new_content = note.content
        
        # Calcular diferencias
        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()
        
        diff = list(difflib.unified_diff(old_lines, new_lines, lineterm=''))
        
        for line in diff:
            if line.startswith('+') and not line.startswith('+++'):
                characters_added += len(line) - 1
                words_added += len(line.split()) - 1
            elif line.startswith('-') and not line.startswith('---'):
                characters_removed += len(line) - 1
                words_removed += len(line.split()) - 1
    
    # Crear la versión
    NoteVersion.objects.create(
        note=note,
        version_number=version_number,
        title=note.title,
        content=note.content,
        content_html=note.content_html,
        change_summary=change_summary,
        created_by=user,
        characters_added=characters_added,
        characters_removed=characters_removed,
        words_added=words_added,
        words_removed=words_removed
    )
    
    # Limpiar versiones antiguas si hay demasiadas
    from django.conf import settings
    max_versions = getattr(settings, 'MAX_NOTE_VERSIONS', 50)
    
    versions_to_delete = note.versions.all()[max_versions:]
    for version in versions_to_delete:
        version.delete()


@receiver(post_delete, sender=Note)
def note_post_delete(sender, instance, **kwargs):
    """Signal después de eliminar una nota."""
    
    # Crear log de auditoría
    AuditLog.objects.create(
        user=getattr(instance, '_deleted_by', None),
        action='delete',
        model_name='Note',
        app_label='notes',
        content_type=ContentType.objects.get_for_model(instance),
        object_id=str(instance.pk),
        description=f'Nota eliminada: {instance.title}',
        old_values={
            'title': instance.title,
            'status': instance.status,
            'visibility': instance.visibility,
        }
    )


@receiver(post_save, sender=NoteCollaborator)
def note_collaborator_post_save(sender, instance, created, **kwargs):
    """Signal después de crear/actualizar colaborador."""
    
    if created:
        # Nuevo colaborador agregado
        
        # Crear notificación
        try:
            notification_type = NotificationType.objects.get(name='note_shared')
            Notification.objects.create(
                recipient=instance.user,
                sender=instance.invited_by,
                notification_type=notification_type,
                title=f'Nueva nota compartida: {instance.note.title}',
                message=f'{instance.invited_by.display_name} compartió la nota "{instance.note.title}" contigo.',
                content_object=instance.note,
                action_url=f'/notes/{instance.note.id}/',
                action_text='Ver nota'
            )
        except NotificationType.DoesNotExist:
            pass
        
        # Crear log de auditoría
        AuditLog.objects.create(
            user=instance.invited_by,
            action='share',
            model_name='Note',
            app_label='notes',
            content_type=ContentType.objects.get_for_model(instance.note),
            object_id=str(instance.note.pk),
            description=f'Nota compartida con {instance.user.display_name}',
            new_values={
                'collaborator': instance.user.display_name,
                'permission': instance.permission
            }
        )
        
        # Notificar por WebSocket
        notify_user_event(instance.user, 'note_shared', {
            'note_id': str(instance.note.id),
            'note_title': instance.note.title,
            'shared_by': instance.invited_by.display_name,
            'permission': instance.permission
        })


@receiver(post_save, sender=Comment)
def comment_post_save(sender, instance, created, **kwargs):
    """Signal después de crear/actualizar comentario."""
    
    if created:
        # Nuevo comentario creado
        
        # Actualizar contador de comentarios de la nota
        instance.note.comment_count = instance.note.comments.count()
        instance.note.save(update_fields=['comment_count'])
        
        # Notificar al autor de la nota (si no es el mismo que comenta)
        if instance.author != instance.note.author:
            try:
                notification_type = NotificationType.objects.get(name='note_commented')
                Notification.objects.create(
                    recipient=instance.note.author,
                    sender=instance.author,
                    notification_type=notification_type,
                    title=f'Nuevo comentario en: {instance.note.title}',
                    message=f'{instance.author.display_name} comentó en tu nota "{instance.note.title}".',
                    content_object=instance.note,
                    action_url=f'/notes/{instance.note.id}/#comment-{instance.id}',
                    action_text='Ver comentario'
                )
            except NotificationType.DoesNotExist:
                pass
        
        # Notificar a otros colaboradores
        collaborators = instance.note.collaborators.exclude(
            id__in=[instance.author.id, instance.note.author.id]
        ).filter(notecollaborator__is_active=True)
        
        for collaborator in collaborators:
            try:
                notification_type = NotificationType.objects.get(name='note_commented')
                Notification.objects.create(
                    recipient=collaborator,
                    sender=instance.author,
                    notification_type=notification_type,
                    title=f'Nuevo comentario en: {instance.note.title}',
                    message=f'{instance.author.display_name} comentó en la nota "{instance.note.title}".',
                    content_object=instance.note,
                    action_url=f'/notes/{instance.note.id}/#comment-{instance.id}',
                    action_text='Ver comentario'
                )
            except NotificationType.DoesNotExist:
                pass
        
        # Crear log de auditoría
        AuditLog.objects.create(
            user=instance.author,
            action='create',
            model_name='Comment',
            app_label='notes',
            content_type=ContentType.objects.get_for_model(instance),
            object_id=str(instance.pk),
            description=f'Comentario creado en nota: {instance.note.title}',
            new_values={
                'content': instance.content[:100] + '...' if len(instance.content) > 100 else instance.content,
                'note_title': instance.note.title
            }
        )
        
        # Notificar por WebSocket
        notify_note_event(instance.note, 'comment_added', {
            'comment_id': str(instance.id),
            'note_id': str(instance.note.id),
            'author': instance.author.display_name,
            'content': instance.content
        })


@receiver(post_delete, sender=Comment)
def comment_post_delete(sender, instance, **kwargs):
    """Signal después de eliminar comentario."""
    
    # Actualizar contador de comentarios de la nota
    try:
        note = instance.note
        note.comment_count = note.comments.count()
        note.save(update_fields=['comment_count'])
    except:
        pass


@receiver(post_save, sender=NoteView)
def note_view_post_save(sender, instance, created, **kwargs):
    """Signal después de registrar una visualización."""
    
    if created:
        # Actualizar contador de vistas de la nota
        note = instance.note
        note.view_count = note.note_views.count()
        note.save(update_fields=['view_count'])


def notify_note_event(note, event_type, data):
    """Notificar evento de nota por WebSocket."""
    
    channel_layer = get_channel_layer()
    
    # Notificar al autor
    group_name = f"user_notes_{note.author.id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'note_event',
            'event_type': event_type,
            'data': data
        }
    )
    
    # Notificar a colaboradores
    for collaborator in note.collaborators.filter(notecollaborator__is_active=True):
        group_name = f"user_notes_{collaborator.id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'note_event',
                'event_type': event_type,
                'data': data
            }
        )


def notify_note_collaborators(note, event_type, data):
    """Notificar a colaboradores de una nota."""
    
    channel_layer = get_channel_layer()
    
    # Notificar a colaboradores activos
    for collaborator in note.collaborators.filter(notecollaborator__is_active=True):
        group_name = f"user_notifications_{collaborator.id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification',
                'event_type': event_type,
                'data': data
            }
        )


def notify_user_event(user, event_type, data):
    """Notificar evento a un usuario específico."""
    
    channel_layer = get_channel_layer()
    group_name = f"user_notifications_{user.id}"
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'notification',
            'event_type': event_type,
            'data': data
        }
    )
