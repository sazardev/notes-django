from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Crear router para ViewSets
router = DefaultRouter()
router.register(r'', views.UserViewSet, basename='users')

app_name = 'users'

urlpatterns = [
    # URLs del router
    path('', include(router.urls)),
    
    # URLs específicas de autenticación
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/change-password/', views.ChangePasswordView.as_view(), name='change-password'),
    path('auth/profile/', views.ProfileView.as_view(), name='profile'),
    
    # URLs para preferencias
    path('preferences/', views.UserPreferencesView.as_view(), name='preferences'),
    
    # URLs para sesiones
    path('sessions/', views.UserSessionListView.as_view(), name='sessions'),
    path('sessions/<uuid:pk>/terminate/', views.TerminateSessionView.as_view(), name='terminate-session'),
]
