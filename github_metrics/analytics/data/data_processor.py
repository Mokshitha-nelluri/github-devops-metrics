"""
Data Processing Service
Handles data transformation, cleaning, and preparation for analytics
"""
import logging
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


class DataProcessor:
    """
    Advanced data processing for analytics
    Focuses on data transformation, cleaning, and preparation
    """
    
    def __init__(self):
        self.cache = {}
    
    def process_metrics_time_series(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process metrics data into time series format for analysis
        """
        try:
            if not metrics_data:
                return {'error': 'No metrics data provided'}
            
            # Convert to DataFrame for easier processing
            df = pd.DataFrame(metrics_data)
            
            # Ensure date column is datetime
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
            else:
                return {'error': 'No date column found in metrics data'}
            
            # Fill missing values and handle data quality issues
            df = self._clean_metrics_data(df)
            
            # Create time series analysis
            time_series = {
                'data': df.to_dict('records'),
                'summary_stats': self._calculate_summary_statistics(df),
                'data_quality': self._assess_data_quality(df),
                'time_range': {
                    'start': df['date'].min().isoformat() if not df.empty else None,
                    'end': df['date'].max().isoformat() if not df.empty else None,
                    'total_days': (df['date'].max() - df['date'].min()).days if not df.empty else 0
                }
            }
            
            return time_series
            
        except Exception as e:
            logger.error(f"Error processing metrics time series: {e}")
            return {'error': str(e)}
    
    def _clean_metrics_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean and normalize metrics data"""
        
        # Define numeric columns that should be cleaned
        numeric_columns = [
            'total_commits', 'total_prs', 'contributions_score', 
            'activity_score', 'lead_time_hours', 'deployment_frequency'
        ]
        
        # Clean numeric columns
        for col in numeric_columns:
            if col in df.columns:
                # Convert to numeric, coercing errors to NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
                # Fill NaN values with 0 for count-type metrics
                if col in ['total_commits', 'total_prs']:
                    df[col] = df[col].fillna(0)
                else:
                    # For score-type metrics, use forward fill then backward fill
                    df[col] = df[col].fillna(method='ffill').fillna(method='bfill').fillna(0)
                
                # Remove outliers (values > 99th percentile)
                if len(df) > 10:  # Only if we have enough data
                    upper_limit = df[col].quantile(0.99)
                    df[col] = df[col].clip(upper=upper_limit)
        
        return df
    
    def _calculate_summary_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Calculate comprehensive summary statistics"""
        
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        stats = {}
        
        for col in numeric_columns:
            if col in df.columns and not df[col].empty:
                stats[col] = {
                    'mean': float(df[col].mean()),
                    'median': float(df[col].median()),
                    'std': float(df[col].std()),
                    'min': float(df[col].min()),
                    'max': float(df[col].max()),
                    'q25': float(df[col].quantile(0.25)),
                    'q75': float(df[col].quantile(0.75)),
                    'skewness': float(df[col].skew()) if len(df) > 2 else 0,
                    'trend': self._calculate_trend(df[col].values)
                }
        
        return stats
    
    def _assess_data_quality(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Assess data quality metrics"""
        
        total_rows = len(df)
        if total_rows == 0:
            return {'quality_score': 0, 'issues': ['No data available']}
        
        issues = []
        quality_indicators = {}
        
        # Check for missing values
        missing_counts = df.isnull().sum()
        missing_percentage = (missing_counts / total_rows * 100).round(2)
        
        for col, pct in missing_percentage.items():
            if pct > 20:  # More than 20% missing
                issues.append(f"High missing data in {col}: {pct}%")
            quality_indicators[f'{col}_missing_pct'] = pct
        
        # Check for data consistency
        if 'date' in df.columns:
            # Check for date gaps
            date_diffs = df['date'].diff().dt.days
            large_gaps = date_diffs[date_diffs > 7]  # Gaps > 7 days
            if len(large_gaps) > 0:
                issues.append(f"Found {len(large_gaps)} date gaps > 7 days")
        
        # Check for data variance (all zeros or constants)
        numeric_columns = df.select_dtypes(include=[np.number]).columns
        for col in numeric_columns:
            if df[col].std() == 0:
                issues.append(f"No variance in {col} (all values are the same)")
        
        # Calculate overall quality score
        quality_score = 100
        quality_score -= len(issues) * 10  # Deduct 10 points per issue
        quality_score -= sum(pct for pct in missing_percentage.values()) / len(missing_percentage)  # Deduct for missing data
        quality_score = max(0, quality_score)
        
        return {
            'quality_score': round(quality_score, 2),
            'issues': issues,
            'missing_data': missing_percentage.to_dict(),
            'total_rows': total_rows,
            'quality_indicators': quality_indicators
        }
    
    def _calculate_trend(self, values: np.ndarray) -> str:
        """Calculate trend direction using linear regression"""
        if len(values) < 3:
            return 'insufficient_data'
        
        # Simple linear trend
        x = np.arange(len(values))
        slope = np.polyfit(x, values, 1)[0]
        
        if slope > np.std(values) * 0.1:  # Significant positive trend
            return 'increasing'
        elif slope < -np.std(values) * 0.1:  # Significant negative trend
            return 'decreasing'
        else:
            return 'stable'
    
    def aggregate_by_time_period(self, metrics_data: List[Dict[str, Any]], 
                                period: str = 'week') -> Dict[str, Any]:
        """
        Aggregate metrics data by time periods (daily, weekly, monthly)
        """
        try:
            df = pd.DataFrame(metrics_data)
            
            if 'date' not in df.columns:
                return {'error': 'No date column found'}
            
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
            
            # Define aggregation rules
            agg_rules = {
                'total_commits': 'sum',
                'total_prs': 'sum',
                'contributions_score': 'mean',
                'activity_score': 'mean',
                'lead_time_hours': 'mean',
                'deployment_frequency': 'mean'
            }
            
            # Filter to only existing columns
            agg_rules = {k: v for k, v in agg_rules.items() if k in df.columns}
            
            if period == 'week':
                aggregated = df.resample('W').agg(agg_rules)
            elif period == 'month':
                aggregated = df.resample('M').agg(agg_rules)
            elif period == 'day':
                aggregated = df.resample('D').agg(agg_rules)
            else:
                return {'error': f'Unsupported period: {period}'}
            
            # Convert back to records
            aggregated = aggregated.fillna(0)
            aggregated_data = aggregated.reset_index().to_dict('records')
            
            # Convert datetime objects to ISO strings
            for record in aggregated_data:
                if 'date' in record:
                    record['date'] = record['date'].isoformat()
            
            return {
                'period': period,
                'data': aggregated_data,
                'summary': {
                    'total_periods': len(aggregated_data),
                    'date_range': {
                        'start': df.index.min().isoformat(),
                        'end': df.index.max().isoformat()
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error aggregating by time period: {e}")
            return {'error': str(e)}
    
    def normalize_metrics(self, metrics_data: List[Dict[str, Any]], 
                         method: str = 'z_score') -> Dict[str, Any]:
        """
        Normalize metrics for comparison and analysis
        """
        try:
            df = pd.DataFrame(metrics_data)
            
            # Select numeric columns for normalization
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            
            if len(numeric_columns) == 0:
                return {'error': 'No numeric columns found for normalization'}
            
            normalized_df = df.copy()
            
            for col in numeric_columns:
                if method == 'z_score':
                    # Z-score normalization
                    mean_val = df[col].mean()
                    std_val = df[col].std()
                    if std_val > 0:
                        normalized_df[f'{col}_normalized'] = (df[col] - mean_val) / std_val
                    else:
                        normalized_df[f'{col}_normalized'] = 0
                        
                elif method == 'min_max':
                    # Min-max normalization (0-1 range)
                    min_val = df[col].min()
                    max_val = df[col].max()
                    if max_val > min_val:
                        normalized_df[f'{col}_normalized'] = (df[col] - min_val) / (max_val - min_val)
                    else:
                        normalized_df[f'{col}_normalized'] = 0
                        
                elif method == 'percentile':
                    # Percentile rank normalization
                    normalized_df[f'{col}_normalized'] = df[col].rank(pct=True)
            
            return {
                'method': method,
                'data': normalized_df.to_dict('records'),
                'normalized_columns': [f'{col}_normalized' for col in numeric_columns]
            }
            
        except Exception as e:
            logger.error(f"Error normalizing metrics: {e}")
            return {'error': str(e)}
    
    def detect_data_patterns(self, metrics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Detect patterns and relationships in metrics data
        """
        try:
            df = pd.DataFrame(metrics_data)
            
            if df.empty:
                return {'error': 'No data provided'}
            
            patterns = {}
            
            # Correlation analysis
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            if len(numeric_columns) >= 2:
                correlation_matrix = df[numeric_columns].corr()
                
                # Find strong correlations (>0.7 or <-0.7)
                strong_correlations = []
                for i in range(len(correlation_matrix.columns)):
                    for j in range(i+1, len(correlation_matrix.columns)):
                        corr_val = correlation_matrix.iloc[i, j]
                        if abs(corr_val) > 0.7:
                            strong_correlations.append({
                                'metric1': correlation_matrix.columns[i],
                                'metric2': correlation_matrix.columns[j],
                                'correlation': round(corr_val, 3),
                                'strength': 'strong' if abs(corr_val) > 0.8 else 'moderate'
                            })
                
                patterns['correlations'] = {
                    'matrix': correlation_matrix.round(3).to_dict(),
                    'strong_correlations': strong_correlations
                }
            
            # Cyclical patterns (day of week, etc.)
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df['day_of_week'] = df['date'].dt.day_name()
                df['week_of_year'] = df['date'].dt.isocalendar().week
                
                # Analyze weekly patterns
                if 'total_commits' in df.columns:
                    weekly_pattern = df.groupby('day_of_week')['total_commits'].mean()
                    patterns['weekly_commit_pattern'] = weekly_pattern.to_dict()
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error detecting data patterns: {e}")
            return {'error': str(e)}