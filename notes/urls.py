from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Crear router para ViewSets
router = DefaultRouter()
router.register(r'notes', views.NoteViewSet, basename='notes')
router.register(r'categories', views.CategoryViewSet, basename='categories')
router.register(r'tags', views.TagViewSet, basename='tags')

app_name = 'notes'

urlpatterns = [
    # URLs del router
    path('api/', include(router.urls)),
    
    # URLs adicionales si necesitamos funciones específicas
    # path('api/notes/search/', views.advanced_search, name='advanced-search'),
    # path('api/notes/export/', views.bulk_export, name='bulk-export'),
]
