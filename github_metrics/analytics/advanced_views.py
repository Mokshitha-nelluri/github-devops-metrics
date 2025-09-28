"""
Advanced Analytics Views
Enhanced analytics using the specialized analytics services
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.services import DataService, GitHubService
from core.models import User
from .github import AdvancedGitHubAnalyzer
from .data import DataProcessor
from .ml import MLService

logger = logging.getLogger(__name__)


class AdvancedRepositoryAnalysisView(APIView):
    """
    Advanced repository ecosystem analysis
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Perform advanced repository analysis"""
        try:
            repo_full_name = request.data.get('repository')
            if not repo_full_name:
                return Response({
                    'error': 'repository parameter is required'
                }, status=400)
            
            owner, name = repo_full_name.split('/', 1)
            
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            if not user.github_token:
                return Response({
                    'error': 'GitHub token not found. Please re-authenticate.'
                }, status=400)
            
            # Initialize services
            github_service = GitHubService(user.github_token)
            analyzer = AdvancedGitHubAnalyzer(github_service)
            
            # Perform comprehensive analysis
            analysis = analyzer.analyze_repository_ecosystem(owner, name)
            
            return Response({
                'repository': repo_full_name,
                'analysis': analysis,
                'analyzed_by': user.email,
                'analysis_type': 'ecosystem'
            })
            
        except Exception as e:
            logger.error(f"Advanced repository analysis error: {e}")
            return Response({
                'error': 'Advanced analysis failed',
                'details': str(e)
            }, status=500)


class DataProcessingView(APIView):
    """
    Advanced data processing and transformation
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Process and analyze metrics data"""
        try:
            processing_type = request.data.get('type', 'time_series')
            period = request.data.get('period', 'week')
            limit = int(request.data.get('limit', 30))
            
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            # Get metrics data
            data_service = DataService()
            metrics_data = data_service.get_user_metrics(str(user.id), limit)
            
            if not metrics_data:
                return Response({
                    'error': 'No metrics data available',
                    'message': 'Please calculate metrics first'
                }, status=400)
            
            # Initialize processor
            processor = DataProcessor()
            
            if processing_type == 'time_series':
                result = processor.process_metrics_time_series(metrics_data)
            elif processing_type == 'aggregate':
                result = processor.aggregate_by_time_period(metrics_data, period)
            elif processing_type == 'normalize':
                method = request.data.get('method', 'z_score')
                result = processor.normalize_metrics(metrics_data, method)
            elif processing_type == 'patterns':
                result = processor.detect_data_patterns(metrics_data)
            else:
                return Response({
                    'error': 'Invalid processing type',
                    'available_types': ['time_series', 'aggregate', 'normalize', 'patterns']
                }, status=400)
            
            return Response({
                'user_id': str(user.id),
                'processing_type': processing_type,
                'result': result,
                'data_points_processed': len(metrics_data)
            })
            
        except Exception as e:
            logger.error(f"Data processing error: {e}")
            return Response({
                'error': 'Data processing failed',
                'details': str(e)
            }, status=500)


class ComprehensiveAnalyticsView(APIView):
    """
    Comprehensive analytics combining all services
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get comprehensive analytics dashboard"""
        try:
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            # Initialize services
            data_service = DataService()
            processor = DataProcessor()
            ml_service = MLService()
            
            # Get data
            metrics_data = data_service.get_user_metrics(str(user.id), 60)  # 2 months
            
            if not metrics_data:
                return Response({
                    'error': 'No analytics data available',
                    'message': 'Please calculate metrics first'
                }, status=400)
            
            comprehensive_analytics = {}
            
            # 1. Data Processing Analysis
            try:
                time_series_analysis = processor.process_metrics_time_series(metrics_data)
                comprehensive_analytics['time_series'] = time_series_analysis
                
                # Weekly aggregation
                weekly_data = processor.aggregate_by_time_period(metrics_data, 'week')
                comprehensive_analytics['weekly_trends'] = weekly_data
                
                # Pattern detection
                patterns = processor.detect_data_patterns(metrics_data)
                comprehensive_analytics['patterns'] = patterns
                
            except Exception as e:
                logger.warning(f"Data processing analysis failed: {e}")
                comprehensive_analytics['data_processing'] = {'error': str(e)}
            
            # 2. Machine Learning Analysis
            try:
                if len(metrics_data) >= 10:
                    # Anomaly detection
                    anomalies = ml_service.detect_anomalies(metrics_data, str(user.id))
                    comprehensive_analytics['anomalies'] = anomalies
                    
                    # Forecasting
                    forecast = ml_service.forecast_trends(metrics_data, 'total_commits', 30)
                    comprehensive_analytics['forecast'] = forecast
                else:
                    comprehensive_analytics['ml_analysis'] = {
                        'available': False,
                        'reason': 'Need at least 10 data points'
                    }
            except Exception as e:
                logger.warning(f"ML analysis failed: {e}")
                comprehensive_analytics['ml_analysis'] = {'error': str(e)}
            
            # 3. Performance Summary
            latest_metrics = metrics_data[0] if metrics_data else {}
            performance_summary = {
                'current_performance': {
                    'grade': latest_metrics.get('performance_grade', {}).get('overall_grade', 'N/A'),
                    'total_commits': latest_metrics.get('total_commits', 0),
                    'total_prs': latest_metrics.get('total_prs', 0),
                    'lead_time': latest_metrics.get('lead_time_hours', 0),
                    'work_life_balance': latest_metrics.get('work_life_balance_score', 0)
                },
                'improvement_areas': latest_metrics.get('performance_grade', {}).get('improvement_areas', []),
                'strengths': latest_metrics.get('performance_grade', {}).get('strengths', [])
            }
            comprehensive_analytics['performance_summary'] = performance_summary
            
            return Response({
                'user_id': str(user.id),
                'analysis_period': '60 days',
                'data_points': len(metrics_data),
                'comprehensive_analytics': comprehensive_analytics,
                'analysis_timestamp': metrics_data[0].get('date') if metrics_data else None
            })
            
        except Exception as e:
            logger.error(f"Comprehensive analytics error: {e}")
            return Response({
                'error': 'Comprehensive analytics failed',
                'details': str(e)
            }, status=500)