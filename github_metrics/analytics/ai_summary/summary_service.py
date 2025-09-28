"""
AI Summary Service for Django
Adapted from backend/summary_bot.py
"""
import logging
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
import hashlib

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from django.conf import settings

logger = logging.getLogger(__name__)


class SummaryService:
    """
    AI-powered summary service for Django application
    Adapted from AISummaryBot
    """
    
    # Performance thresholds
    LEAD_TIME_ELITE = 24
    LEAD_TIME_EXCELLENT = 48
    DEPLOY_FREQ_EXCELLENT = 10
    DEPLOY_FREQ_LOW = 2
    FAILURE_RATE_ELITE = 5
    FAILURE_RATE_ALERT = 15
    WLB_ALERT = 50
    
    def __init__(self):
        """Initialize AI summary service"""
        self.gemini_api_key = getattr(settings, 'GEMINI_API_KEY', None) or os.getenv('GEMINI_API_KEY')
        self.gemini_available = GEMINI_AVAILABLE and self.gemini_api_key
        
        if self.gemini_available:
            try:
                genai.configure(api_key=self.gemini_api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                logger.info("Gemini AI initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize Gemini AI: {e}")
                self.gemini_available = False
        else:
            logger.info("Gemini AI not available, using fallback summaries")
    
    def generate_performance_summary(self, metrics: Dict[str, Any], user_email: str) -> Dict[str, Any]:
        """Generate comprehensive performance summary"""
        try:
            if self.gemini_available:
                return self._generate_ai_summary(metrics, user_email)
            else:
                return self._generate_fallback_summary(metrics, user_email)
        except Exception as e:
            logger.error(f"Error generating performance summary: {e}")
            return self._generate_fallback_summary(metrics, user_email)
    
    def _generate_ai_summary(self, metrics: Dict[str, Any], user_email: str) -> Dict[str, Any]:
        """Generate AI-powered summary using Gemini"""
        try:
            # Prepare metrics data for AI analysis
            summary_data = self._prepare_metrics_for_ai(metrics)
            
            prompt = f"""
            As a DevOps performance analyst, provide a comprehensive but concise performance summary for a developer.
            
            Developer Metrics:
            {summary_data}
            
            Please provide:
            1. Overall Performance Assessment (2-3 sentences)
            2. Top 3 Strengths
            3. Top 3 Areas for Improvement
            4. Specific Actionable Recommendations
            5. Performance Trend Analysis
            
            Keep the tone professional but encouraging. Focus on actionable insights.
            Format as JSON with keys: assessment, strengths, improvements, recommendations, trends
            """
            
            response = self.model.generate_content(prompt)
            
            if response and response.text:
                # Try to parse as JSON, fallback to structured text
                try:
                    import json
                    ai_summary = json.loads(response.text)
                except:
                    # If JSON parsing fails, create structured response from text
                    ai_summary = {
                        "assessment": response.text[:500],
                        "strengths": ["AI analysis completed successfully"],
                        "improvements": ["Continue current development practices"],
                        "recommendations": ["Maintain consistent contribution patterns"],
                        "trends": "Overall positive development activity"
                    }
                
                return {
                    "summary_type": "ai_generated",
                    "generated_at": datetime.now().isoformat(),
                    "user_email": user_email,
                    "ai_summary": ai_summary,
                    "metrics_snapshot": self._get_metrics_snapshot(metrics)
                }
            else:
                logger.warning("Empty AI response, falling back to rule-based summary")
                return self._generate_fallback_summary(metrics, user_email)
                
        except Exception as e:
            logger.error(f"AI summary generation failed: {e}")
            return self._generate_fallback_summary(metrics, user_email)
    
    def _generate_fallback_summary(self, metrics: Dict[str, Any], user_email: str) -> Dict[str, Any]:
        """Generate rule-based summary as fallback"""
        
        # Extract key metrics
        dora = metrics.get("dora", {})
        lead_time = dora.get("lead_time", {}).get("total_lead_time_hours", 0)
        deploy_freq = dora.get("deployment_frequency", {}).get("per_week", 0)
        failure_rate = dora.get("change_failure_rate", {}).get("percentage", 0)
        
        code_quality = metrics.get("code_quality", {})
        review_coverage = code_quality.get("review_coverage_percentage", 0)
        
        productivity = metrics.get("productivity_patterns", {})
        wlb_score = productivity.get("work_life_balance_score", 0)
        
        performance_grade = metrics.get("performance_grade", {})
        overall_grade = performance_grade.get("overall_grade", "C")
        
        # Generate assessment
        if overall_grade in ["A+", "A", "A-"]:
            assessment = "Excellent performance with strong DORA metrics and development practices."
        elif overall_grade in ["B+", "B", "B-"]:
            assessment = "Good performance with room for improvement in key areas."
        else:
            assessment = "Performance needs attention across multiple development metrics."
        
        # Identify strengths
        strengths = []
        if lead_time <= self.LEAD_TIME_ELITE:
            strengths.append("Elite lead time performance - changes move to production very quickly")
        if deploy_freq >= self.DEPLOY_FREQ_EXCELLENT:
            strengths.append("High deployment frequency indicating good development velocity")
        if failure_rate <= self.FAILURE_RATE_ELITE:
            strengths.append("Low change failure rate showing high code quality")
        if review_coverage >= 80:
            strengths.append("Strong code review practices with high coverage")
        if wlb_score >= 70:
            strengths.append("Good work-life balance with healthy development patterns")
        
        if not strengths:
            strengths = ["Consistent development activity", "Active contribution to projects"]
        
        # Identify improvements
        improvements = []
        if lead_time > self.LEAD_TIME_EXCELLENT:
            improvements.append("Reduce lead time by streamlining development and review processes")
        if deploy_freq < self.DEPLOY_FREQ_LOW:
            improvements.append("Increase deployment frequency for faster feedback cycles")
        if failure_rate > self.FAILURE_RATE_ALERT:
            improvements.append("Focus on code quality to reduce change failure rate")
        if review_coverage < 50:
            improvements.append("Implement more thorough code review processes")
        if wlb_score < self.WLB_ALERT:
            improvements.append("Consider work-life balance - reduce late night and weekend work")
        
        if not improvements:
            improvements = ["Maintain current development practices", "Continue learning new technologies"]
        
        # Generate recommendations
        recommendations = []
        if lead_time > 72:
            recommendations.append("Break down large changes into smaller, reviewable chunks")
        if deploy_freq < 1:
            recommendations.append("Adopt continuous deployment practices")
        if failure_rate > 15:
            recommendations.append("Implement automated testing and quality gates")
        
        if not recommendations:
            recommendations = ["Continue current development practices", "Explore new development tools and techniques"]
        
        # Trend analysis
        trends = f"Performance grade: {overall_grade}. "
        if deploy_freq > 5:
            trends += "High development activity. "
        elif deploy_freq > 1:
            trends += "Moderate development activity. "
        else:
            trends += "Low development activity. "
        
        return {
            "summary_type": "rule_based",
            "generated_at": datetime.now().isoformat(),
            "user_email": user_email,
            "ai_summary": {
                "assessment": assessment,
                "strengths": strengths[:3],  # Top 3
                "improvements": improvements[:3],  # Top 3
                "recommendations": recommendations[:3],  # Top 3
                "trends": trends
            },
            "metrics_snapshot": self._get_metrics_snapshot(metrics)
        }
    
    def _prepare_metrics_for_ai(self, metrics: Dict[str, Any]) -> str:
        """Prepare metrics data for AI analysis"""
        dora = metrics.get("dora", {})
        code_quality = metrics.get("code_quality", {})
        productivity = metrics.get("productivity_patterns", {})
        collaboration = metrics.get("collaboration", {})
        performance = metrics.get("performance_grade", {})
        
        summary_text = f"""
        DORA Metrics:
        - Lead Time: {dora.get("lead_time", {}).get("total_lead_time_hours", 0):.1f} hours
        - Deployment Frequency: {dora.get("deployment_frequency", {}).get("per_week", 0):.1f} per week
        - Change Failure Rate: {dora.get("change_failure_rate", {}).get("percentage", 0):.1f}%
        - MTTR: {dora.get("mttr", {}).get("mttr_hours", 0):.1f} hours
        
        Code Quality:
        - Review Coverage: {code_quality.get("review_coverage_percentage", 0):.1f}%
        - Average PR Size: {code_quality.get("avg_pr_size", 0):.0f} lines
        - Large PRs: {code_quality.get("large_prs_percentage", 0):.1f}%
        
        Productivity:
        - Work-Life Balance Score: {productivity.get("work_life_balance_score", 0):.1f}
        - Weekend Work: {productivity.get("weekend_work_percentage", 0):.1f}%
        - Late Night Work: {productivity.get("late_night_work_percentage", 0):.1f}%
        
        Collaboration:
        - Unique Reviewers: {collaboration.get("unique_reviewers", 0)}
        - Reviews per PR: {collaboration.get("reviews_per_pr", 0):.1f}
        
        Performance Grade: {performance.get("overall_grade", "N/A")} ({performance.get("percentage", 0):.1f}%)
        """
        
        return summary_text
    
    def _get_metrics_snapshot(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Get key metrics snapshot for summary"""
        return {
            "total_commits": metrics.get("total_commits", 0),
            "total_prs": metrics.get("total_prs", 0),
            "lead_time_hours": metrics.get("lead_time_hours", 0),
            "deployment_frequency": metrics.get("deployment_frequency", 0),
            "change_failure_rate": metrics.get("change_failure_rate", 0),
            "performance_grade": metrics.get("performance_grade", {}).get("overall_grade", "N/A")
        }