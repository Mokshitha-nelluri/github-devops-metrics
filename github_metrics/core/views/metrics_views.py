"""
Metrics calculation and analysis views
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.services import DataService, GitHubService, MetricsService
from core.models import User
from analytics.ml import MLService
from analytics.ai_summary import SummaryService

logger = logging.getLogger(__name__)


class CalculateMetricsView(APIView):
    """
    Calculate metrics for user repositories
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """Calculate and store metrics"""
        try:
            scope = request.data.get('scope', 'tracked')  # 'tracked' or 'global'
            repo_full_name = request.data.get('repo_full_name')  # For single repo analysis
            
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
            metrics_service = MetricsService()
            data_service = DataService()
            
            if repo_full_name:
                # Calculate metrics for specific repository
                owner, name = repo_full_name.split('/', 1)
                
                commits = github_service.fetch_commits(owner, name, user.email)
                pull_requests = github_service.fetch_pull_requests(owner, name, user.email)
                repo_insights = github_service.fetch_repository_insights(owner, name)
                
                # Calculate metrics
                metrics = metrics_service.calculate_all_metrics(commits, pull_requests, 'repository')
                
                # Add repository insights
                metrics.update(repo_insights)
                
                # Save repository metrics
                data_service.save_repo_metrics(owner, name, metrics)
                
                return Response({
                    'success': True,
                    'repository': repo_full_name,
                    'metrics': metrics,
                    'commits_analyzed': len(commits),
                    'prs_analyzed': len(pull_requests)
                })
            
            else:
                # Calculate metrics for all tracked repositories
                repos = data_service.get_user_repos(str(user.id))
                
                if not repos:
                    return Response({
                        'error': 'No repositories found. Please add repositories to track.'
                    }, status=400)
                
                all_commits = []
                all_prs = []
                repo_results = []
                
                for repo_data in repos:
                    repo_info = repo_data['repos']
                    owner = repo_info['owner']
                    name = repo_info['name']
                    
                    try:
                        commits = github_service.fetch_commits(owner, name, user.email)
                        prs = github_service.fetch_pull_requests(owner, name, user.email)
                        
                        all_commits.extend(commits)
                        all_prs.extend(prs)
                        
                        repo_results.append({
                            'repository': f"{owner}/{name}",
                            'commits': len(commits),
                            'prs': len(prs)
                        })
                        
                    except Exception as e:
                        logger.warning(f"Failed to fetch data for {owner}/{name}: {e}")
                        repo_results.append({
                            'repository': f"{owner}/{name}",
                            'error': str(e)
                        })
                
                # Calculate comprehensive metrics
                metrics = metrics_service.calculate_all_metrics(all_commits, all_prs, scope)
                
                # Save user metrics
                data_service.save_user_metrics(user.email, metrics)
                
                return Response({
                    'success': True,
                    'scope': scope,
                    'metrics': metrics,
                    'repositories_analyzed': repo_results,
                    'total_commits': len(all_commits),
                    'total_prs': len(all_prs)
                })
                
        except Exception as e:
            logger.error(f"Error calculating metrics: {e}")
            return Response({
                'error': 'Failed to calculate metrics',
                'details': str(e)
            }, status=500)


class MetricsHistoryView(APIView):
    """
    Get metrics history and analytics
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get metrics history with analytics"""
        try:
            repo_full_name = request.query_params.get('repository')
            limit = int(request.query_params.get('limit', 30))
            include_analytics = request.query_params.get('analytics', 'false').lower() == 'true'
            
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            data_service = DataService()
            
            if repo_full_name:
                # Get repository metrics
                owner, name = repo_full_name.split('/', 1)
                metrics = data_service.get_repo_metrics(owner, name, limit)
                
                response_data = {
                    'repository': repo_full_name,
                    'metrics': metrics,
                    'total_count': len(metrics)
                }
                
            else:
                # Get user metrics
                metrics = data_service.get_user_metrics(str(user.id), limit)
                
                response_data = {
                    'user_id': str(user.id),
                    'metrics': metrics,
                    'total_count': len(metrics)
                }
                
                # Add analytics if requested
                if include_analytics and metrics:
                    try:
                        ml_service = MLService()
                        summary_service = SummaryService()
                        
                        # Anomaly detection
                        anomalies = ml_service.detect_anomalies(metrics, str(user.id))
                        
                        # Trend forecasting
                        forecast = ml_service.forecast_trends(metrics, 'total_commits')
                        
                        # AI summary (if latest metrics available)
                        if metrics:
                            latest_metrics = metrics[0] if isinstance(metrics[0], dict) else {}
                            ai_summary = summary_service.generate_performance_summary(
                                latest_metrics, user.email
                            )
                        else:
                            ai_summary = None
                        
                        response_data['analytics'] = {
                            'anomalies': anomalies,
                            'forecast': forecast,
                            'ai_summary': ai_summary
                        }
                        
                    except Exception as e:
                        logger.warning(f"Analytics generation failed: {e}")
                        response_data['analytics'] = {
                            'error': f'Analytics unavailable: {str(e)}'
                        }
            
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Error getting metrics history: {e}")
            return Response({
                'error': 'Failed to get metrics history',
                'details': str(e)
            }, status=500)