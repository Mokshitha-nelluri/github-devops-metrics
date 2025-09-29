"""
Utility functions for analytics operations
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import logging
from analytics.constants import (
    DATA_BATCH_SIZE,
    API_MAX_PAGE_SIZE,
    METRICS_CACHE_TIMEOUT
)

logger = logging.getLogger(__name__)


def batch_process_data(data: List[Any], batch_size: int = None) -> List[List[Any]]:
    """Split data into batches for processing"""
    if batch_size is None:
        batch_size = DATA_BATCH_SIZE
    
    batches = []
    for i in range(0, len(data), batch_size):
        batch = data[i:i + batch_size]
        batches.append(batch)
    
    return batches


def validate_github_data(data: Dict[str, Any]) -> bool:
    """Validate GitHub API response data"""
    required_fields = ['id', 'name']
    
    for field in required_fields:
        if field not in data:
            logger.warning(f"Missing required field: {field}")
            return False
    
    return True


def format_metrics_response(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Format metrics data for API response"""
    try:
        formatted = {
            'deployment_frequency': round(metrics.get('deployment_frequency', 0), 2),
            'lead_time_hours': round(metrics.get('lead_time_for_changes', 0), 2),
            'mttr_hours': round(metrics.get('mean_time_to_recovery', 0), 2),
            'change_failure_rate': round(metrics.get('change_failure_rate', 0), 2),
            'total_commits': metrics.get('total_commits', 0),
            'total_prs': metrics.get('total_prs', 0),
            'performance_grade': metrics.get('performance_grade', {}),
            'calculated_at': metrics.get('calculated_at')
        }
        
        return formatted
        
    except Exception as e:
        logger.error(f"Error formatting metrics response: {str(e)}")
        return {}


def calculate_date_range(days_back: int) -> tuple:
    """Calculate date range for data queries"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    return start_date, end_date


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers, returning default if denominator is zero"""
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default


def parse_github_date(date_string: str) -> Optional[datetime]:
    """Parse GitHub API date string to datetime object"""
    try:
        if not date_string:
            return None
            
        # Handle Z suffix
        if date_string.endswith('Z'):
            date_string = date_string.replace('Z', '+00:00')
            
        return datetime.fromisoformat(date_string)
        
    except (ValueError, TypeError) as e:
        logger.warning(f"Error parsing date '{date_string}': {str(e)}")
        return None


def filter_recent_items(items: List[Dict], date_field: str, days_back: int) -> List[Dict]:
    """Filter items to only include recent ones"""
    cutoff_date = datetime.now() - timedelta(days=days_back)
    recent_items = []
    
    for item in items:
        item_date = parse_github_date(item.get(date_field, ''))
        if item_date and item_date > cutoff_date:
            recent_items.append(item)
    
    return recent_items


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile of a list of values"""
    if not values:
        return 0.0
    
    sorted_values = sorted(values)
    index = (percentile / 100) * (len(sorted_values) - 1)
    
    if index.is_integer():
        return sorted_values[int(index)]
    else:
        lower = sorted_values[int(index)]
        upper = sorted_values[int(index) + 1]
        return lower + (upper - lower) * (index - int(index))


def aggregate_metrics_by_period(metrics_data: List[Dict], period: str = 'week') -> Dict[str, List]:
    """Aggregate metrics data by time period"""
    try:
        from collections import defaultdict
        
        period_data = defaultdict(list)
        
        for metric in metrics_data:
            date_str = metric.get('calculated_at') or metric.get('date', '')
            metric_date = parse_github_date(date_str)
            
            if not metric_date:
                continue
            
            if period == 'week':
                # Get start of week (Monday)
                week_start = metric_date - timedelta(days=metric_date.weekday())
                period_key = week_start.strftime('%Y-W%U')
            elif period == 'month':
                period_key = metric_date.strftime('%Y-%m')
            elif period == 'day':
                period_key = metric_date.strftime('%Y-%m-%d')
            else:
                period_key = metric_date.strftime('%Y-%m-%d')
            
            period_data[period_key].append(metric)
        
        return dict(period_data)
        
    except Exception as e:
        logger.error(f"Error aggregating metrics by period: {str(e)}")
        return {}


def detect_outliers(values: List[float], method: str = 'iqr') -> List[int]:
    """Detect outliers in a list of values"""
    try:
        import statistics
        
        if len(values) < 4:
            return []
        
        outlier_indices = []
        
        if method == 'iqr':
            # Interquartile Range method
            q1 = calculate_percentile(values, 25)
            q3 = calculate_percentile(values, 75)
            iqr = q3 - q1
            
            lower_bound = q1 - 1.5 * iqr
            upper_bound = q3 + 1.5 * iqr
            
            for i, value in enumerate(values):
                if value < lower_bound or value > upper_bound:
                    outlier_indices.append(i)
                    
        elif method == 'zscore':
            # Z-score method
            mean_val = statistics.mean(values)
            std_val = statistics.stdev(values) if len(values) > 1 else 0
            
            if std_val > 0:
                for i, value in enumerate(values):
                    z_score = abs((value - mean_val) / std_val)
                    if z_score > 3:  # 3 standard deviations
                        outlier_indices.append(i)
        
        return outlier_indices
        
    except Exception as e:
        logger.error(f"Error detecting outliers: {str(e)}")
        return []


def generate_cache_key(prefix: str, *args) -> str:
    """Generate cache key from prefix and arguments"""
    key_parts = [prefix] + [str(arg) for arg in args]
    return '_'.join(key_parts)


def log_performance_metrics(func_name: str, duration: float, **kwargs):
    """Log performance metrics for monitoring"""
    log_data = {
        'function': func_name,
        'duration_seconds': round(duration, 3),
        **kwargs
    }
    
    if duration > 5.0:  # Log slow operations
        logger.warning(f"Slow operation detected: {log_data}")
    else:
        logger.debug(f"Performance metrics: {log_data}")