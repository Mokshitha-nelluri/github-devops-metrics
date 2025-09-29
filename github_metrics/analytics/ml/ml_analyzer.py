"""
ML Analysis Service for Django
Adapted from backend/ml_analyzer.py
"""
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, r2_score
from datetime import datetime, timedelta
import logging
from typing import Dict, List, Any, Tuple, Optional
import warnings
import pickle
import os
from django.conf import settings

warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)


class MLService:
    """
    Machine Learning service for Django application
    Simplified version of EnhancedMLAnalyzer
    """
    
    def __init__(self):
        self.scalers = {}
        self.models = {}
        self.anomaly_detectors = {}
        
        # Create models directory in Django
        self.model_save_path = os.path.join(settings.BASE_DIR, 'ml_models')
        if not os.path.exists(self.model_save_path):
            os.makedirs(self.model_save_path)
    
    def detect_anomalies(self, metrics_data: List[Dict[str, Any]], user_id: str) -> Dict[str, Any]:
        """Detect anomalies in metrics data"""
        try:
            if len(metrics_data) < 10:
                return {
                    "anomalies": [],
                    "status": "insufficient_data",
                    "message": "Need at least 10 data points for anomaly detection"
                }
            
            # Prepare data for anomaly detection
            df = pd.DataFrame(metrics_data)
            
            # Select numeric columns for anomaly detection
            numeric_columns = ['total_commits', 'total_prs', 'contributions_score', 'activity_score']
            available_columns = [col for col in numeric_columns if col in df.columns]
            
            if not available_columns:
                return {
                    "anomalies": [],
                    "status": "no_numeric_data",
                    "message": "No numeric metrics available for anomaly detection"
                }
            
            # Prepare feature matrix
            X = df[available_columns].fillna(0).values
            
            # Use or create anomaly detector
            detector_key = f"anomaly_{user_id}"
            if detector_key not in self.anomaly_detectors:
                self.anomaly_detectors[detector_key] = IsolationForest(
                    contamination=0.1,
                    random_state=42
                )
                self.anomaly_detectors[detector_key].fit(X)
            
            # Detect anomalies
            anomaly_scores = self.anomaly_detectors[detector_key].decision_function(X)
            anomalies = self.anomaly_detectors[detector_key].predict(X)
            
            # Identify anomalous points
            anomaly_indices = np.where(anomalies == -1)[0]
            
            anomaly_results = []
            for idx in anomaly_indices:
                anomaly_results.append({
                    "date": df.iloc[idx].get("date", ""),
                    "anomaly_score": float(anomaly_scores[idx]),
                    "metrics": df.iloc[idx][available_columns].to_dict(),
                    "severity": "high" if anomaly_scores[idx] < -0.5 else "medium"
                })
            
            return {
                "anomalies": anomaly_results,
                "total_anomalies": len(anomaly_results),
                "anomaly_rate": len(anomaly_results) / len(metrics_data) * 100,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error detecting anomalies: {e}")
            return {
                "anomalies": [],
                "status": "error",
                "message": str(e)
            }
    
    def forecast_trends(self, metrics_data: List[Dict[str, Any]], metric_name: str, days_ahead: int = 30) -> Dict[str, Any]:
        """Simple trend forecasting"""
        try:
            if len(metrics_data) < 5:
                return {
                    "forecast": [],
                    "status": "insufficient_data",
                    "message": "Need at least 5 data points for forecasting"
                }
            
            df = pd.DataFrame(metrics_data)
            
            if metric_name not in df.columns:
                return {
                    "forecast": [],
                    "status": "metric_not_found",
                    "message": f"Metric '{metric_name}' not found in data"
                }
            
            # Simple linear trend
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')
            
            # Convert dates to numeric for linear regression
            df['date_numeric'] = (df['date'] - df['date'].min()).dt.days
            
            # Fit simple linear model
            X = df['date_numeric'].values.reshape(-1, 1)
            y = df[metric_name].fillna(0).values
            
            from sklearn.linear_model import LinearRegression
            model = LinearRegression()
            model.fit(X, y)
            
            # Generate future dates
            last_date = df['date'].max()
            future_dates = [last_date + timedelta(days=i) for i in range(1, days_ahead + 1)]
            future_numeric = [(last_date + timedelta(days=i) - df['date'].min()).days for i in range(1, days_ahead + 1)]
            
            # Make predictions
            future_X = np.array(future_numeric).reshape(-1, 1)
            predictions = model.predict(future_X)
            
            forecast_results = []
            for i, (date, pred) in enumerate(zip(future_dates, predictions)):
                forecast_results.append({
                    "date": date.strftime("%Y-%m-%d"),
                    "predicted_value": float(pred),
                    "confidence": max(0, 1 - (i / days_ahead) * 0.5)  # Decreasing confidence
                })
            
            # Calculate trend
            slope = model.coef_[0]
            trend_direction = "increasing" if slope > 0.1 else "decreasing" if slope < -0.1 else "stable"
            
            return {
                "forecast": forecast_results,
                "trend_direction": trend_direction,
                "trend_strength": abs(float(slope)),
                "model_score": float(model.score(X, y)),
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error forecasting trends: {e}")
            return {
                "forecast": [],
                "status": "error",
                "message": str(e)
            }
    
    def cluster_performance(self, user_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Cluster users by performance patterns"""
        try:
            if len(user_metrics) < 3:
                return {
                    "clusters": [],
                    "status": "insufficient_data",
                    "message": "Need at least 3 users for clustering"
                }
            
            df = pd.DataFrame(user_metrics)
            
            # Select features for clustering
            feature_columns = ['total_commits', 'total_prs', 'contributions_score', 'activity_score']
            available_columns = [col for col in feature_columns if col in df.columns]
            
            if len(available_columns) < 2:
                return {
                    "clusters": [],
                    "status": "insufficient_features",
                    "message": "Need at least 2 numeric features for clustering"
                }
            
            # Prepare and scale data
            X = df[available_columns].fillna(0).values
            scaler = StandardScaler()
            X_scaled = scaler.fit_transform(X)
            
            # Perform clustering
            from sklearn.cluster import KMeans
            n_clusters = min(3, len(user_metrics))
            kmeans = KMeans(n_clusters=n_clusters, random_state=42)
            cluster_labels = kmeans.fit_predict(X_scaled)
            
            # Analyze clusters
            df['cluster'] = cluster_labels
            
            cluster_analysis = []
            for cluster_id in range(n_clusters):
                cluster_data = df[df['cluster'] == cluster_id]
                
                cluster_stats = {}
                for col in available_columns:
                    cluster_stats[col] = {
                        "mean": float(cluster_data[col].mean()),
                        "std": float(cluster_data[col].std()),
                        "count": int(len(cluster_data))
                    }
                
                # Determine cluster characteristics
                avg_commits = cluster_stats.get('total_commits', {}).get('mean', 0)
                avg_prs = cluster_stats.get('total_prs', {}).get('mean', 0)
                
                if avg_commits > 50 and avg_prs > 10:
                    cluster_type = "high_activity"
                elif avg_commits > 20 and avg_prs > 5:
                    cluster_type = "moderate_activity"
                else:
                    cluster_type = "low_activity"
                
                cluster_analysis.append({
                    "cluster_id": cluster_id,
                    "cluster_type": cluster_type,
                    "size": len(cluster_data),
                    "characteristics": cluster_stats,
                    "users": cluster_data.get('email', cluster_data.index).tolist() if 'email' in cluster_data.columns else []
                })
            
            return {
                "clusters": cluster_analysis,
                "total_clusters": n_clusters,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error clustering performance: {e}")
            return {
                "clusters": [],
                "status": "error",
                "message": str(e)
            }