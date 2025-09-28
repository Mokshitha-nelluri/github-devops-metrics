"""
Continuous ML Learning System
Migrated from backend/continuous_ml_learning.py for Django
"""
import os
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
import joblib
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import io

from core.services import DataService
from core.models import User

logger = logging.getLogger(__name__)


class ContinuousMLLearningSystem:
    """
    Django-based continuous ML learning system
    Handles incremental model training and intelligent data processing
    """
    
    def __init__(self):
        self.models_dir = os.path.join(settings.MEDIA_ROOT, "ml_models")
        self.min_training_samples = 50  # Minimum new samples to trigger retraining
        self.retrain_interval_days = 7  # Minimum days between retraining
        self.model_versions = {}  # Track model versions per user
        
        # Ensure models directory exists
        os.makedirs(self.models_dir, exist_ok=True)
        
        self.data_service = DataService()
        
    def get_user_model_path(self, user_email: str, model_type: str) -> str:
        """Get file path for user's specific model"""
        safe_email = user_email.replace('@', '_at_').replace('.', '_dot_')
        return os.path.join(self.models_dir, f"{safe_email}_{model_type}_model.pkl")
        
    def get_user_scaler_path(self, user_email: str) -> str:
        """Get file path for user's data scaler"""
        safe_email = user_email.replace('@', '_at_').replace('.', '_dot_')
        return os.path.join(self.models_dir, f"{safe_email}_scaler.pkl")
        
    def get_model_metadata_path(self, user_email: str) -> str:
        """Get file path for model metadata"""
        safe_email = user_email.replace('@', '_at_').replace('.', '_dot_')
        return os.path.join(self.models_dir, f"{safe_email}_metadata.pkl")
        
    def should_retrain_model(self, user_email: str) -> bool:
        """
        Determine if model should be retrained based on:
        1. Amount of new data since last training
        2. Time since last training
        3. Model performance degradation
        """
        try:
            metadata_path = self.get_model_metadata_path(user_email)
            
            if not os.path.exists(metadata_path):
                logger.info(f"No existing model for {user_email}, retraining needed")
                return True
                
            # Load metadata
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
                
            last_training_date = metadata.get('last_training_date')
            last_data_count = metadata.get('data_count', 0)
            
            # Check time since last training
            if last_training_date:
                days_since_training = (datetime.now() - last_training_date).days
                if days_since_training >= self.retrain_interval_days:
                    logger.info(f"Retraining {user_email} model - {days_since_training} days since last training")
                    return True
                    
            # Check amount of new data
            user = User.objects.get(email=user_email)
            current_data = self.data_service.get_user_metrics(str(user.id), limit=200)
            current_count = len(current_data)
            
            new_samples = current_count - last_data_count
            if new_samples >= self.min_training_samples:
                logger.info(f"Retraining {user_email} model - {new_samples} new samples available")
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Error checking retrain status for {user_email}: {e}")
            return False
            
    def prepare_training_data(self, user_email: str) -> Optional[Tuple[np.ndarray, np.ndarray]]:
        """
        Prepare training data from user's historical metrics
        """
        try:
            user = User.objects.get(email=user_email)
            metrics_data = self.data_service.get_user_metrics(str(user.id), limit=500)
            
            if len(metrics_data) < 10:
                logger.warning(f"Insufficient data for {user_email}: {len(metrics_data)} samples")
                return None
                
            # Convert to DataFrame
            df = pd.DataFrame(metrics_data)
            
            # Feature engineering
            features = []
            targets = []
            
            for _, row in df.iterrows():
                try:
                    # Extract features
                    feature_row = [
                        row.get('total_commits', 0),
                        row.get('total_prs', 0),
                        row.get('lead_time_hours', 0),
                        row.get('deployment_frequency_weekly', 0),
                        row.get('change_failure_rate', 0),
                        row.get('mttr_hours', 0),
                        row.get('work_life_balance_score', 50),
                    ]
                    
                    # Target: Overall performance score
                    performance_grade = row.get('performance_grade', {})
                    target_score = performance_grade.get('percentage', 70)
                    
                    features.append(feature_row)
                    targets.append(target_score)
                    
                except Exception as e:
                    logger.warning(f"Skipping row due to error: {e}")
                    continue
                    
            if len(features) < 10:
                logger.warning(f"Insufficient valid samples for {user_email}: {len(features)}")
                return None
                
            return np.array(features), np.array(targets)
            
        except Exception as e:
            logger.error(f"Error preparing training data for {user_email}: {e}")
            return None
            
    def train_user_model(self, user_email: str) -> bool:
        """
        Train or retrain ML model for specific user
        """
        try:
            logger.info(f"Starting model training for {user_email}")
            
            # Prepare data
            training_data = self.prepare_training_data(user_email)
            if training_data is None:
                return False
                
            features, targets = training_data
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                features, targets, test_size=0.2, random_state=42
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            
            model.fit(X_train_scaled, y_train)
            
            # Evaluate model
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            
            logger.info(f"Model trained for {user_email} - Train: {train_score:.3f}, Test: {test_score:.3f}")
            
            # Save model
            model_path = self.get_user_model_path(user_email, "performance")
            with open(model_path, 'wb') as f:
                joblib.dump(model, f)
                
            # Save scaler
            scaler_path = self.get_user_scaler_path(user_email)
            with open(scaler_path, 'wb') as f:
                joblib.dump(scaler, f)
                
            # Save metadata
            metadata = {
                'last_training_date': datetime.now(),
                'data_count': len(features),
                'train_score': train_score,
                'test_score': test_score,
                'model_version': datetime.now().strftime('%Y%m%d_%H%M%S')
            }
            
            metadata_path = self.get_model_metadata_path(user_email)
            with open(metadata_path, 'wb') as f:
                pickle.dump(metadata, f)
                
            self.model_versions[user_email] = metadata['model_version']
            
            logger.info(f"Model successfully saved for {user_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error training model for {user_email}: {e}")
            return False
            
    def predict_performance(self, user_email: str, metrics_data: Dict) -> Optional[Dict]:
        """
        Make performance predictions using user's personalized model
        """
        try:
            model_path = self.get_user_model_path(user_email, "performance")
            scaler_path = self.get_user_scaler_path(user_email)
            
            if not os.path.exists(model_path) or not os.path.exists(scaler_path):
                logger.warning(f"No trained model found for {user_email}")
                return None
                
            # Load model and scaler
            with open(model_path, 'rb') as f:
                model = joblib.load(f)
                
            with open(scaler_path, 'rb') as f:
                scaler = joblib.load(f)
                
            # Prepare features
            features = np.array([[
                metrics_data.get('total_commits', 0),
                metrics_data.get('total_prs', 0),
                metrics_data.get('lead_time_hours', 0),
                metrics_data.get('deployment_frequency_weekly', 0),
                metrics_data.get('change_failure_rate', 0),
                metrics_data.get('mttr_hours', 0),
                metrics_data.get('work_life_balance_score', 50),
            ]])
            
            # Scale and predict
            features_scaled = scaler.transform(features)
            prediction = model.predict(features_scaled)[0]
            
            # Get prediction confidence (simplified)
            # Use prediction variance from forest
            if hasattr(model, 'estimators_'):
                predictions = [estimator.predict(features_scaled)[0] for estimator in model.estimators_]
                confidence = 1.0 / (1.0 + np.std(predictions))
            else:
                confidence = 0.8  # Default confidence
                
            return {
                'predicted_performance_score': round(prediction, 1),
                'confidence': round(confidence, 3),
                'model_version': self.model_versions.get(user_email, 'unknown'),
                'prediction_date': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error making prediction for {user_email}: {e}")
            return None
            
    def auto_retrain_if_needed(self, user_email: str) -> bool:
        """
        Automatically retrain model if conditions are met
        """
        try:
            if self.should_retrain_model(user_email):
                return self.train_user_model(user_email)
            return True
            
        except Exception as e:
            logger.error(f"Error in auto-retrain for {user_email}: {e}")
            return False
            
    def get_model_status(self, user_email: str) -> Dict:
        """
        Get current model status and metadata
        """
        try:
            metadata_path = self.get_model_metadata_path(user_email)
            
            if not os.path.exists(metadata_path):
                return {
                    'model_exists': False,
                    'status': 'No model trained yet'
                }
                
            with open(metadata_path, 'rb') as f:
                metadata = pickle.load(f)
                
            return {
                'model_exists': True,
                'last_training_date': metadata.get('last_training_date'),
                'data_count': metadata.get('data_count'),
                'train_score': metadata.get('train_score'),
                'test_score': metadata.get('test_score'),
                'model_version': metadata.get('model_version'),
                'needs_retraining': self.should_retrain_model(user_email)
            }
            
        except Exception as e:
            logger.error(f"Error getting model status for {user_email}: {e}")
            return {
                'model_exists': False,
                'error': str(e)
            }
            
    def cleanup_old_models(self, days_old: int = 30) -> int:
        """
        Clean up old model files to save space
        """
        try:
            deleted_count = 0
            cutoff_date = datetime.now() - timedelta(days=days_old)
            
            for filename in os.listdir(self.models_dir):
                file_path = os.path.join(self.models_dir, filename)
                
                if os.path.isfile(file_path):
                    file_modified = datetime.fromtimestamp(os.path.getmtime(file_path))
                    
                    if file_modified < cutoff_date:
                        os.remove(file_path)
                        deleted_count += 1
                        logger.info(f"Deleted old model file: {filename}")
                        
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error cleaning up old models: {e}")
            return 0


# Global learning system instance
_learning_system = None

def get_learning_system() -> ContinuousMLLearningSystem:
    """Get global learning system instance"""
    global _learning_system
    if _learning_system is None:
        _learning_system = ContinuousMLLearningSystem()
    return _learning_system