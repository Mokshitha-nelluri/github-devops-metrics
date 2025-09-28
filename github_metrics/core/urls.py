"""
Core app URL configuration
"""
from django.urls import path, include
from .views import (
    GitHubAuthView, AuthCallbackView, LogoutView,
    UserProfileView, UserRepositoriesView, UserMetricsView,
    CalculateMetricsView, MetricsHistoryView, DashboardView
)

app_name = 'core'

urlpatterns = [
    # Dashboard
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    
    # Authentication
    path('auth/github/', GitHubAuthView.as_view(), name='github_auth'),
    path('auth/callback/', AuthCallbackView.as_view(), name='auth_callback'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    
    # User management
    path('user/profile/', UserProfileView.as_view(), name='user_profile'),
    path('user/repositories/', UserRepositoriesView.as_view(), name='user_repositories'),
    path('user/metrics/', UserMetricsView.as_view(), name='user_metrics'),
    
    # Metrics
    path('metrics/calculate/', CalculateMetricsView.as_view(), name='calculate_metrics'),
    path('metrics/history/', MetricsHistoryView.as_view(), name='metrics_history'),
]