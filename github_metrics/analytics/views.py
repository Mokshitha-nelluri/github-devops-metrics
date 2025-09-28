"""
Analytics views
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.services import DataService, GitHubService
from core.models import User
from .ml import MLService
from .ai_summary import SummaryService
from .github import AdvancedGitHubAnalyzer
from .data import DataProcessor

logger = logging.getLogger(__name__)


class MLAnalysisView(APIView):
    """
    Machine Learning analysis endpoints
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, analysis_type=None):
        """Get ML analysis results"""
        try:
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            data_service = DataService()
            ml_service = MLService()
            
            # Get user metrics
            limit = int(request.query_params.get('limit', 30))
            metrics_data = data_service.get_user_metrics(str(user.id), limit)
            
            if not metrics_data:
                return Response({
                    'error': 'No metrics data available',
                    'message': 'Please calculate metrics first'
                }, status=400)
            
            if analysis_type == 'anomalies':
                # Anomaly detection
                result = ml_service.detect_anomalies(metrics_data, str(user.id))
                
            elif analysis_type == 'forecast':
                # Trend forecasting
                metric_name = request.query_params.get('metric', 'total_commits')
                days_ahead = int(request.query_params.get('days', 30))
                result = ml_service.forecast_trends(metrics_data, metric_name, days_ahead)
                
            elif analysis_type == 'clusters':
                # Performance clustering (need multiple users' data)
                # For now, return user's performance profile
                result = {
                    'status': 'success',
                    'user_profile': {
                        'user_id': str(user.id),
                        'metrics_count': len(metrics_data),
                        'performance_summary': metrics_data[0] if metrics_data else {}
                    },
                    'message': 'Clustering requires multiple users data'
                }
                
            else:
                return Response({
                    'error': 'Invalid analysis type',
                    'available_types': ['anomalies', 'forecast', 'clusters']
                }, status=400)
            
            return Response({
                'analysis_type': analysis_type,
                'user_id': str(user.id),
                'result': result
            })
            
        except Exception as e:
            logger.error(f"ML analysis error: {e}")
            return Response({
                'error': 'ML analysis failed',
                'details': str(e)
            }, status=500)


class AISummaryView(APIView):
    """
    AI-powered performance summary
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get AI performance summary"""
        try:
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            data_service = DataService()
            summary_service = SummaryService()
            
            # Get latest metrics
            metrics_data = data_service.get_user_metrics(str(user.id), 1)
            
            if not metrics_data:
                return Response({
                    'error': 'No metrics data available',
                    'message': 'Please calculate metrics first'
                }, status=400)
            
            latest_metrics = metrics_data[0]
            
            # Generate AI summary
            summary = summary_service.generate_performance_summary(
                latest_metrics, user.email
            )
            
            return Response({
                'user_id': str(user.id),
                'summary': summary,
                'based_on_date': latest_metrics.get('date', 'unknown')
            })
            
        except Exception as e:
            logger.error(f"AI summary error: {e}")
            return Response({
                'error': 'AI summary generation failed',
                'details': str(e)
            }, status=500)
    
    def post(self, request):
        """Generate new AI summary"""
        try:
            # Same as GET but forces regeneration
            force_regenerate = request.data.get('force_regenerate', True)
            
            return self.get(request)
            
        except Exception as e:
            logger.error(f"AI summary generation error: {e}")
            return Response({
                'error': 'Failed to generate AI summary',
                'details': str(e)
            }, status=500)


class AnalyticsDashboardView(APIView):
    """
    Comprehensive analytics dashboard
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get analytics dashboard data"""
        try:
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            data_service = DataService()
            ml_service = MLService()
            summary_service = SummaryService()
            
            # Get metrics data
            metrics_data = data_service.get_user_metrics(str(user.id), 30)
            
            if not metrics_data:
                return Response({
                    'error': 'No analytics data available',
                    'message': 'Please calculate metrics first to see analytics'
                }, status=400)
            
            dashboard_data = {
                'user_id': str(user.id),
                'data_period': '30 days',
                'total_metrics_points': len(metrics_data)
            }
            
            # Add ML analysis if enough data
            if len(metrics_data) >= 10:
                try:
                    # Anomaly detection
                    anomalies = ml_service.detect_anomalies(metrics_data, str(user.id))
                    dashboard_data['anomaly_analysis'] = anomalies
                    
                    # Trend forecasting
                    forecast = ml_service.forecast_trends(metrics_data, 'total_commits', 14)
                    dashboard_data['commit_forecast'] = forecast
                    
                except Exception as e:
                    logger.warning(f"ML analysis failed: {e}")
                    dashboard_data['ml_analysis'] = {'error': str(e)}
            else:
                dashboard_data['ml_analysis'] = {
                    'available': False,
                    'reason': 'Need at least 10 data points for ML analysis'
                }
            
            # Add AI summary if data available
            try:
                latest_metrics = metrics_data[0]
                ai_summary = summary_service.generate_performance_summary(
                    latest_metrics, user.email
                )
                dashboard_data['ai_summary'] = ai_summary
            except Exception as e:
                logger.warning(f"AI summary failed: {e}")
                dashboard_data['ai_summary'] = {'error': str(e)}
            
            # Performance trends
            if len(metrics_data) >= 2:
                current = metrics_data[0]
                previous = metrics_data[1]
                
                trends = {
                    'commits': {
                        'current': current.get('total_commits', 0),
                        'previous': previous.get('total_commits', 0),
                        'change': current.get('total_commits', 0) - previous.get('total_commits', 0)
                    },
                    'prs': {
                        'current': current.get('total_prs', 0),
                        'previous': previous.get('total_prs', 0),
                        'change': current.get('total_prs', 0) - previous.get('total_prs', 0)
                    },
                    'performance_grade': {
                        'current': current.get('performance_grade', {}).get('overall_grade', 'N/A'),
                        'previous': previous.get('performance_grade', {}).get('overall_grade', 'N/A')
                    }
                }
                dashboard_data['trends'] = trends
            
            return Response(dashboard_data)
            
        except Exception as e:
            logger.error(f"Analytics dashboard error: {e}")
            return Response({
                'error': 'Failed to load analytics dashboard',
                'details': str(e)
            }, status=500)