"""
Dashboard and summary views
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.services import DataService
from core.models import User
from analytics.ml import MLService
from analytics.ai_summary import SummaryService

logger = logging.getLogger(__name__)


class DashboardView(APIView):
    """
    Main dashboard view with comprehensive metrics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get dashboard data"""
        try:
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            data_service = DataService()
            
            # Get recent metrics (last 30 days)
            recent_metrics = data_service.get_user_metrics(str(user.id), 30)
            
            # Get user repositories
            repositories = data_service.get_user_repos(str(user.id))
            
            # Prepare dashboard summary
            dashboard_data = {
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'github_username': user.github_username,
                    'name': user.name,
                    'avatar_url': user.avatar_url
                },
                'repositories': {
                    'total_count': len(repositories),
                    'repositories': repositories[:10]  # Show first 10
                },
                'recent_metrics': {
                    'total_count': len(recent_metrics),
                    'metrics': recent_metrics[:7] if recent_metrics else []  # Last 7 days
                }
            }
            
            # Add summary statistics if metrics available
            if recent_metrics:
                latest_metrics = recent_metrics[0] if recent_metrics else {}
                
                dashboard_data['summary'] = {
                    'total_commits': latest_metrics.get('total_commits', 0),
                    'total_prs': latest_metrics.get('total_prs', 0),
                    'performance_grade': latest_metrics.get('performance_grade', {}).get('overall_grade', 'N/A'),
                    'lead_time_hours': latest_metrics.get('lead_time_hours', 0),
                    'deployment_frequency': latest_metrics.get('deployment_frequency', 0),
                    'work_life_balance_score': latest_metrics.get('work_life_balance_score', 0)
                }
                
                # Add trend analysis
                if len(recent_metrics) >= 2:
                    previous_metrics = recent_metrics[1]
                    current_commits = latest_metrics.get('total_commits', 0)
                    previous_commits = previous_metrics.get('total_commits', 0)
                    
                    commit_trend = 'stable'
                    if current_commits > previous_commits * 1.1:
                        commit_trend = 'increasing'
                    elif current_commits < previous_commits * 0.9:
                        commit_trend = 'decreasing'
                    
                    dashboard_data['trends'] = {
                        'commit_trend': commit_trend,
                        'metrics_available': True
                    }
                else:
                    dashboard_data['trends'] = {
                        'metrics_available': False,
                        'message': 'Need more data points for trend analysis'
                    }
            else:
                dashboard_data['summary'] = {
                    'total_commits': 0,
                    'total_prs': 0,
                    'performance_grade': 'N/A',
                    'lead_time_hours': 0,
                    'deployment_frequency': 0,
                    'work_life_balance_score': 0
                }
                dashboard_data['trends'] = {
                    'metrics_available': False,
                    'message': 'No metrics available. Calculate metrics to see dashboard data.'
                }
            
            # Add quick actions
            dashboard_data['quick_actions'] = [
                {
                    'action': 'calculate_metrics',
                    'title': 'Calculate Metrics',
                    'description': 'Analyze your latest GitHub activity',
                    'enabled': len(repositories) > 0
                },
                {
                    'action': 'add_repository',
                    'title': 'Add Repository',
                    'description': 'Track a new repository',
                    'enabled': True
                },
                {
                    'action': 'view_analytics',
                    'title': 'View Analytics',
                    'description': 'See AI insights and predictions',
                    'enabled': len(recent_metrics) > 5
                }
            ]
            
            return Response(dashboard_data)
            
        except Exception as e:
            logger.error(f"Error getting dashboard data: {e}")
            return Response({
                'error': 'Failed to load dashboard',
                'details': str(e)
            }, status=500)