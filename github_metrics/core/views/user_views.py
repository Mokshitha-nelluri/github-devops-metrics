"""
User-related views
"""
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated

from core.services import DataService, GitHubService
from core.models import User

logger = logging.getLogger(__name__)


class UserProfileView(APIView):
    """
    Get and update user profile information
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user profile"""
        try:
            data_service = DataService()
            
            # Get user by Django user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({
                    'error': 'User profile not found'
                }, status=404)
            
            return Response({
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'github_username': user.github_username,
                    'name': user.name,
                    'avatar_url': user.avatar_url,
                    'created_at': user.created_at.isoformat(),
                    'updated_at': user.updated_at.isoformat()
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return Response({
                'error': 'Failed to get user profile',
                'details': str(e)
            }, status=500)


class UserRepositoriesView(APIView):
    """
    Manage user repositories
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user repositories"""
        try:
            data_service = DataService()
            
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            repos = data_service.get_user_repos(str(user.id))
            
            return Response({
                'repositories': repos,
                'total_count': len(repos)
            })
            
        except Exception as e:
            logger.error(f"Error getting user repositories: {e}")
            return Response({
                'error': 'Failed to get repositories',
                'details': str(e)
            }, status=500)
    
    def post(self, request):
        """Add repository to user's tracking list"""
        try:
            repo_full_name = request.data.get('repo_full_name')
            if not repo_full_name:
                return Response({
                    'error': 'repo_full_name is required'
                }, status=400)
            
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            data_service = DataService()
            success = data_service.save_user_repo(user.email, repo_full_name)
            
            if success:
                return Response({
                    'success': True,
                    'message': f'Repository {repo_full_name} added successfully'
                })
            else:
                return Response({
                    'error': 'Failed to add repository'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Error adding repository: {e}")
            return Response({
                'error': 'Failed to add repository',
                'details': str(e)
            }, status=500)
    
    def delete(self, request):
        """Remove repository from user's tracking list"""
        try:
            user_repo_id = request.data.get('user_repo_id')
            if not user_repo_id:
                return Response({
                    'error': 'user_repo_id is required'
                }, status=400)
            
            data_service = DataService()
            success = data_service.delete_user_repo_by_id(user_repo_id)
            
            if success:
                return Response({
                    'success': True,
                    'message': 'Repository removed successfully'
                })
            else:
                return Response({
                    'error': 'Failed to remove repository'
                }, status=400)
                
        except Exception as e:
            logger.error(f"Error removing repository: {e}")
            return Response({
                'error': 'Failed to remove repository',
                'details': str(e)
            }, status=500)


class UserMetricsView(APIView):
    """
    Get user metrics and history
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get user metrics history"""
        try:
            limit = int(request.query_params.get('limit', 30))
            
            # Get user
            try:
                user = User.objects.get(github_username=request.user.username)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=404)
            
            data_service = DataService()
            metrics = data_service.get_user_metrics(str(user.id), limit)
            
            return Response({
                'metrics': metrics,
                'total_count': len(metrics),
                'user_id': str(user.id)
            })
            
        except Exception as e:
            logger.error(f"Error getting user metrics: {e}")
            return Response({
                'error': 'Failed to get user metrics',
                'details': str(e)
            }, status=500)