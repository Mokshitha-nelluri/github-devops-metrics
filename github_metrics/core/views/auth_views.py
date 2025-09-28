"""
Authentication views for GitHub OAuth integration
"""
import logging
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth import login, logout
from django.contrib.auth.models import User as DjangoUser
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token

from core.services import DataService
from core.models import User

logger = logging.getLogger(__name__)


class GitHubAuthView(APIView):
    """
    Initiate GitHub OAuth flow
    """
    permission_classes = []
    
    def get(self, request):
        """Redirect to GitHub OAuth"""
        github_auth_url = (
            f"https://github.com/login/oauth/authorize"
            f"?client_id={settings.GITHUB_CLIENT_ID}"
            f"&redirect_uri={settings.OAUTH_REDIRECT_URI}"
            f"&scope=repo,user:email"
            f"&state=django_auth"
        )
        
        return Response({
            'auth_url': github_auth_url,
            'message': 'Redirect to this URL to authenticate with GitHub'
        })


@method_decorator(csrf_exempt, name='dispatch')
class AuthCallbackView(View):
    """
    Handle GitHub OAuth callback
    """
    
    def get(self, request):
        """Handle OAuth callback"""
        code = request.GET.get('code')
        state = request.GET.get('state')
        error = request.GET.get('error')
        
        if error:
            logger.error(f"OAuth error: {error}")
            return JsonResponse({
                'error': 'Authentication failed',
                'details': error
            }, status=400)
        
        if not code:
            return JsonResponse({
                'error': 'No authorization code provided'
            }, status=400)
        
        if state != 'django_auth':
            return JsonResponse({
                'error': 'Invalid state parameter'
            }, status=400)
        
        try:
            # Exchange code for access token
            token_data = self._exchange_code_for_token(code)
            if not token_data:
                return JsonResponse({
                    'error': 'Failed to exchange code for token'
                }, status=400)
            
            # Get user info from GitHub
            user_info = self._get_github_user_info(token_data['access_token'])
            if not user_info:
                return JsonResponse({
                    'error': 'Failed to get user information'
                }, status=400)
            
            # Create or update user in database
            user = self._create_or_update_user(user_info, token_data['access_token'])
            if not user:
                return JsonResponse({
                    'error': 'Failed to create user'
                }, status=400)
            
            # Create Django auth token
            django_user, created = DjangoUser.objects.get_or_create(
                username=user.github_username,
                defaults={'email': user.email}
            )
            
            token, created = Token.objects.get_or_create(user=django_user)
            
            # Return success response
            return JsonResponse({
                'success': True,
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'github_username': user.github_username,
                    'name': user.name
                },
                'auth_token': token.key,
                'github_token': token_data['access_token']
            })
            
        except Exception as e:
            logger.error(f"OAuth callback error: {e}")
            return JsonResponse({
                'error': 'Authentication failed',
                'details': str(e)
            }, status=500)
    
    def _exchange_code_for_token(self, code):
        """Exchange authorization code for access token"""
        try:
            token_url = "https://github.com/login/oauth/access_token"
            token_data = {
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.OAUTH_REDIRECT_URI
            }
            
            headers = {
                "Accept": "application/json",
                "User-Agent": "GitHub-Metrics-Django-App"
            }
            
            response = requests.post(token_url, data=token_data, headers=headers)
            response.raise_for_status()
            
            token_info = response.json()
            
            if "access_token" not in token_info:
                logger.error(f"No access token in response: {token_info}")
                return None
            
            return token_info
            
        except Exception as e:
            logger.error(f"Token exchange error: {e}")
            return None
    
    def _get_github_user_info(self, access_token):
        """Get user information from GitHub API"""
        try:
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "GitHub-Metrics-Django-App"
            }
            
            # Get user info
            user_response = requests.get("https://api.github.com/user", headers=headers)
            user_response.raise_for_status()
            user_info = user_response.json()
            
            # Get user emails
            email_response = requests.get("https://api.github.com/user/emails", headers=headers)
            email_response.raise_for_status()
            email_info = email_response.json()
            
            # Find primary email
            primary_email = None
            for email in email_info:
                if email.get("primary", False):
                    primary_email = email["email"]
                    break
            
            if not primary_email:
                primary_email = user_info.get("email")
            
            if not primary_email:
                raise ValueError("Could not determine user's primary email")
            
            user_info["primary_email"] = primary_email
            return user_info
            
        except Exception as e:
            logger.error(f"GitHub user info error: {e}")
            return None
    
    def _create_or_update_user(self, user_info, github_token):
        """Create or update user in database"""
        try:
            data_service = DataService()
            
            email = user_info["primary_email"]
            github_username = user_info.get("login")
            name = user_info.get("name", github_username)
            avatar_url = user_info.get("avatar_url")
            
            # Ensure user exists
            user_id = data_service.ensure_user_exists_and_get_id(
                email=email,
                github_token=github_token,
                github_username=github_username
            )
            
            if user_id:
                # Update additional user info
                user = User.objects.get(id=user_id)
                user.name = name
                user.avatar_url = avatar_url
                user.save(update_fields=['name', 'avatar_url', 'updated_at'])
                
                return user
            
            return None
            
        except Exception as e:
            logger.error(f"User creation error: {e}")
            return None


class LogoutView(APIView):
    """
    Handle user logout
    """
    
    def post(self, request):
        """Logout user"""
        try:
            if request.user.is_authenticated:
                # Delete auth token
                try:
                    request.user.auth_token.delete()
                except:
                    pass
                
                logout(request)
            
            return Response({
                'success': True,
                'message': 'Successfully logged out'
            })
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            return Response({
                'error': 'Logout failed',
                'details': str(e)
            }, status=500)