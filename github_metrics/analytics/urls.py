"""
Analytics app URL configuration
"""
from django.urls import path
from .views import MLAnalysisView, AISummaryView, AnalyticsDashboardView
from .advanced_views import AdvancedRepositoryAnalysisView, DataProcessingView, ComprehensiveAnalyticsView

app_name = 'analytics'

urlpatterns = [
    # Analytics dashboard
    path('dashboard/', AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    
    # ML Analysis
    path('ml/anomalies/', MLAnalysisView.as_view(), {'analysis_type': 'anomalies'}, name='ml_anomalies'),
    path('ml/forecast/', MLAnalysisView.as_view(), {'analysis_type': 'forecast'}, name='ml_forecast'),
    path('ml/clusters/', MLAnalysisView.as_view(), {'analysis_type': 'clusters'}, name='ml_clusters'),
    
    # AI Summary
    path('ai/summary/', AISummaryView.as_view(), name='ai_summary'),
    
    # Advanced Analytics
    path('advanced/repository/', AdvancedRepositoryAnalysisView.as_view(), name='advanced_repository_analysis'),
    path('advanced/data-processing/', DataProcessingView.as_view(), name='advanced_data_processing'),
    path('advanced/comprehensive/', ComprehensiveAnalyticsView.as_view(), name='comprehensive_analytics'),
]