"""
Celery tasks for analytics operations
"""
from typing import Dict, Any, List
from celery import shared_task
from django.utils import timezone
import logging
from .constants import CELERY_TASK_RETRY_DELAY, CELERY_MAX_RETRIES

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=CELERY_MAX_RETRIES)
def refresh_user_metrics_task(self, user_id: int):
    """Celery task to refresh metrics for a specific user"""
    try:
        from analytics.refresh.refresh_manager import refresh_user_now
        result = refresh_user_now(user_id)
        logger.info(f"Completed metrics refresh for user {user_id}")
        return result
    except Exception as e:
        logger.error(f"Error in refresh_user_metrics_task for user {user_id}: {str(e)}")
        raise self.retry(countdown=CELERY_TASK_RETRY_DELAY)


@shared_task(bind=True, max_retries=CELERY_MAX_RETRIES)
def refresh_all_users_task(self):
    """Celery task to refresh metrics for all active users"""
    try:
        from analytics.refresh.refresh_manager import refresh_all_users_now
        result = refresh_all_users_now()
        logger.info("Completed metrics refresh for all users")
        return result
    except Exception as e:
        logger.error(f"Error in refresh_all_users_task: {str(e)}")
        raise self.retry(countdown=CELERY_TASK_RETRY_DELAY)


@shared_task
def cleanup_old_metrics_task():
    """Celery task to cleanup old metrics data"""
    try:
        from analytics.constants import DATA_CLEANUP_DAYS
        from django.utils import timezone
        from datetime import timedelta
        from core.models import UserMetrics
        
        cutoff_date = timezone.now() - timedelta(days=DATA_CLEANUP_DAYS)
        deleted_count = UserMetrics.objects.filter(
            calculated_at__lt=cutoff_date
        ).delete()[0]
        
        logger.info(f"Cleaned up {deleted_count} old metrics records")
        return {'status': 'success', 'deleted_count': deleted_count}
        
    except Exception as e:
        logger.error(f"Error in cleanup_old_metrics_task: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@shared_task
def generate_ai_summary_task(user_id: int):
    """Celery task to generate AI summary for user"""
    try:
        from analytics.ai_assist.summary_bot import SummaryService
        from core.models import User
        
        user = User.objects.get(id=user_id)
        summary_service = SummaryService()
        
        # Get user metrics for summary
        from core.services import DataService
        data_service = DataService()
        metrics_data = data_service.get_user_metrics(str(user_id), limit=30)
        
        if metrics_data:
            # Convert list to dict or use the latest metrics
            if isinstance(metrics_data, list) and metrics_data:
                latest_metrics: Dict[str, Any] = metrics_data[0]
            else:
                latest_metrics: Dict[str, Any] = metrics_data if isinstance(metrics_data, dict) else {}
            summary = summary_service.generate_performance_summary(
                latest_metrics, str(user_id)
            )
            logger.info(f"Generated AI summary for user {user_id}")
            return summary
        else:
            return {'error': 'No metrics data available for summary'}
            
    except Exception as e:
        logger.error(f"Error in generate_ai_summary_task for user {user_id}: {str(e)}")
        return {'error': str(e)}


@shared_task
def ml_analysis_task(user_id: int, analysis_type: str = 'anomalies'):
    """Celery task to run ML analysis for user"""
    try:
        from analytics.ml.ml_analyzer import MLService
        from core.services import DataService
        
        ml_service = MLService()
        data_service = DataService()
        
        # Get user metrics for analysis
        metrics_data = data_service.get_user_metrics(str(user_id), limit=100)
        
        if not metrics_data or len(metrics_data) < 10:
            return {'error': 'Insufficient data for ML analysis'}
        
        if analysis_type == 'anomalies':
            result = ml_service.detect_anomalies(metrics_data, str(user_id))
        elif analysis_type == 'forecast':
            result = ml_service.forecast_trends(metrics_data, 'total_commits', 30)
        elif analysis_type == 'clusters':
            # Get data for multiple users for clustering
            all_users_data = []  # Would need to implement this
            result = ml_service.cluster_performance(all_users_data)
        else:
            return {'error': f'Unknown analysis type: {analysis_type}'}
        
        logger.info(f"Completed {analysis_type} analysis for user {user_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in ml_analysis_task for user {user_id}: {str(e)}")
        return {'error': str(e)}