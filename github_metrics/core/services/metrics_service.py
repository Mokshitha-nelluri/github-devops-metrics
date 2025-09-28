"""
Metrics calculation service
Adapted from backend/metrics_calculator.py for Django
"""
from datetime import datetime, timedelta
import statistics
from typing import Dict, List, Any, Tuple
import logging
import numpy as np
from collections import defaultdict, Counter

logger = logging.getLogger(__name__)


class MetricsService:
    """
    Metrics calculation service for Django application
    Adapted from EnhancedMetricsCalculator
    """
    
    def __init__(self):
        # Industry benchmarks (based on DORA research)
        self.benchmarks = {
            "elite": {
                "lead_time_hours": 24,
                "deployment_frequency_per_week": 10,
                "change_failure_rate": 5,
                "mttr_hours": 1
            },
            "high": {
                "lead_time_hours": 168,  # 1 week
                "deployment_frequency_per_week": 3,
                "change_failure_rate": 10,
                "mttr_hours": 24
            },
            "medium": {
                "lead_time_hours": 720,  # 1 month
                "deployment_frequency_per_week": 1,
                "change_failure_rate": 15,
                "mttr_hours": 168
            }
        }
    
    def calculate_all_metrics(self, commits: List[Dict], pull_requests: List[Dict], scope: str) -> Dict[str, Any]:
        """Calculate comprehensive set of metrics"""
        metrics = {}
        
        # Store raw totals
        metrics["total_commits"] = len(commits)
        metrics["total_prs"] = len(pull_requests)
        
        # DORA metrics
        metrics["dora"] = self.calculate_dora_metrics(commits, pull_requests)
        
        # Code quality
        metrics["code_quality"] = self.calculate_code_quality_metrics(commits, pull_requests)
        
        # Productivity patterns
        metrics["productivity_patterns"] = self.calculate_productivity_patterns(commits)
        
        # Collaboration
        metrics["collaboration"] = self.calculate_collaboration_metrics(pull_requests)
        
        # Performance grade
        metrics["performance_grade"] = self.get_performance_grade(metrics)
        
        # Add calculated values to top level for easier access
        metrics["lead_time_hours"] = metrics["dora"]["lead_time"].get("total_lead_time_hours", 0)
        metrics["deployment_frequency"] = metrics["dora"]["deployment_frequency"].get("per_week", 0)
        metrics["change_failure_rate"] = metrics["dora"]["change_failure_rate"].get("percentage", 0)
        metrics["review_coverage_percentage"] = metrics["code_quality"].get("review_coverage_percentage", 0)
        metrics["work_life_balance_score"] = metrics["productivity_patterns"].get("work_life_balance_score", 0)
        
        return metrics
    
    def calculate_dora_metrics(self, commits: List[Dict], pull_requests: List[Dict]) -> Dict[str, Any]:
        """Calculate DORA metrics"""
        return {
            "lead_time": self._calculate_lead_time(pull_requests),
            "deployment_frequency": self._calculate_deployment_frequency(pull_requests),
            "change_failure_rate": self._calculate_failure_rate(pull_requests, commits),
            "mttr": self._calculate_mttr(pull_requests, commits)
        }
    
    def _calculate_lead_time(self, pull_requests: List[Dict]) -> Dict[str, Any]:
        """Calculate lead time metrics"""
        lead_times = []
        
        for pr in pull_requests:
            if not pr.get("mergedAt"):
                continue
            
            try:
                created_at = self._parse_date(pr["createdAt"])
                merged_at = self._parse_date(pr["mergedAt"])
                
                lead_time = (merged_at - created_at).total_seconds()
                if lead_time >= 0:
                    lead_times.append(lead_time)
            except Exception as e:
                logger.warning(f"Failed to calculate lead time for PR: {e}")
                continue
        
        return {
            "total_lead_time_sec": self._average(lead_times),
            "total_lead_time_hours": self._average(lead_times) / 3600 if lead_times else 0,
            "p50_lead_time_hours": self._percentile(lead_times, 50) / 3600 if lead_times else 0,
            "p90_lead_time_hours": self._percentile(lead_times, 90) / 3600 if lead_times else 0,
            "p95_lead_time_hours": self._percentile(lead_times, 95) / 3600 if lead_times else 0
        }
    
    def _calculate_deployment_frequency(self, pull_requests: List[Dict]) -> Dict[str, Any]:
        """Calculate deployment frequency"""
        if not pull_requests:
            return {"per_week": 0, "per_day": 0}
        
        weekly_deployments = defaultdict(int)
        
        for pr in pull_requests:
            if pr.get("mergedAt"):
                try:
                    merge_date = self._parse_date(pr["mergedAt"])
                    week_key = merge_date.strftime("%Y-W%U")
                    weekly_deployments[week_key] += 1
                except Exception:
                    continue
        
        avg_per_week = sum(weekly_deployments.values()) / len(weekly_deployments) if weekly_deployments else 0
        
        return {
            "per_week": round(avg_per_week, 2),
            "total_deployments": len([pr for pr in pull_requests if pr.get("mergedAt")])
        }
    
    def _calculate_failure_rate(self, pull_requests: List[Dict], commits: List[Dict]) -> Dict[str, Any]:
        """Calculate change failure rate"""
        if not pull_requests:
            return {"percentage": 0}
        
        failure_indicators = ["revert", "rollback", "hotfix", "emergency", "fix", "bug"]
        total_failures = 0
        
        for pr in pull_requests:
            if not pr.get("mergedAt"):
                continue
            
            title = pr.get("title", "").lower()
            body = pr.get("body", "").lower()
            
            if any(keyword in title or keyword in body for keyword in failure_indicators):
                total_failures += 1
        
        failure_rate = (total_failures / len(pull_requests)) * 100 if pull_requests else 0
        
        return {
            "percentage": round(failure_rate, 2),
            "total_failures": total_failures,
            "total_prs": len(pull_requests)
        }
    
    def _calculate_mttr(self, pull_requests: List[Dict], commits: List[Dict]) -> Dict[str, Any]:
        """Calculate Mean Time to Recovery"""
        # Simplified MTTR calculation
        recovery_times = []
        
        sorted_prs = sorted(
            [pr for pr in pull_requests if pr.get("mergedAt")],
            key=lambda x: self._parse_date(x["mergedAt"])
        )
        
        failure_keywords = ["bug", "fix", "issue", "broken", "error", "hotfix"]
        
        for i, pr in enumerate(sorted_prs):
            title = pr.get("title", "").lower()
            
            if any(keyword in title for keyword in failure_keywords):
                fix_time = self._parse_date(pr["mergedAt"])
                
                if i > 0:
                    failure_time = self._parse_date(sorted_prs[i-1]["mergedAt"])
                    recovery_time = (fix_time - failure_time).total_seconds()
                    if recovery_time > 0:
                        recovery_times.append(recovery_time)
        
        avg_mttr = self._average(recovery_times) if recovery_times else 0
        
        return {
            "mttr_hours": avg_mttr / 3600 if avg_mttr else 0,
            "recovery_incidents": len(recovery_times)
        }
    
    def calculate_code_quality_metrics(self, commits: List[Dict], pull_requests: List[Dict]) -> Dict[str, Any]:
        """Calculate code quality metrics"""
        commit_sizes = []
        large_commits = 0
        
        for commit in commits:
            size = (commit.get("additions", 0) + commit.get("deletions", 0))
            commit_sizes.append(size)
            if size > 500:
                large_commits += 1
        
        pr_sizes = []
        large_prs = 0
        
        for pr in pull_requests:
            size = (pr.get("additions", 0) + pr.get("deletions", 0))
            pr_sizes.append(size)
            if size > 1000:
                large_prs += 1
        
        reviewed_prs = sum(1 for pr in pull_requests if pr.get("reviews", {}).get("nodes"))
        review_coverage = (reviewed_prs / len(pull_requests)) * 100 if pull_requests else 0
        
        files_changed = [commit.get("changedFiles", 0) for commit in commits]
        
        return {
            "avg_commit_size": self._average(commit_sizes),
            "avg_pr_size": self._average(pr_sizes),
            "large_commits_percentage": (large_commits / len(commits)) * 100 if commits else 0,
            "large_prs_percentage": (large_prs / len(pull_requests)) * 100 if pull_requests else 0,
            "review_coverage_percentage": round(review_coverage, 2),
            "avg_files_per_commit": self._average(files_changed)
        }
    
    def calculate_productivity_patterns(self, commits: List[Dict]) -> Dict[str, Any]:
        """Analyze productivity patterns"""
        if not commits:
            return {}
        
        commit_times = []
        day_counts = defaultdict(int)
        hour_counts = defaultdict(int)
        
        for commit in commits:
            try:
                commit_date = self._parse_date(commit["committedDate"])
                commit_times.append(commit_date)
                
                day_counts[commit_date.weekday()] += 1
                hour_counts[commit_date.hour] += 1
            except Exception:
                continue
        
        # Work-life balance indicators
        weekend_commits = day_counts[5] + day_counts[6]  # Saturday + Sunday
        weekend_percentage = (weekend_commits / len(commits)) * 100 if commits else 0
        
        late_night_commits = sum(hour_counts[hour] for hour in list(range(22, 24)) + list(range(0, 6)))
        late_night_percentage = (late_night_commits / len(commits)) * 100 if commits else 0
        
        return {
            "commits_by_day": dict(day_counts),
            "commits_by_hour": dict(hour_counts),
            "weekend_work_percentage": round(weekend_percentage, 2),
            "late_night_work_percentage": round(late_night_percentage, 2),
            "most_productive_day": max(day_counts, key=day_counts.get) if day_counts else None,
            "most_productive_hour": max(hour_counts, key=hour_counts.get) if hour_counts else None,
            "work_life_balance_score": max(0, 100 - weekend_percentage - late_night_percentage)
        }
    
    def calculate_collaboration_metrics(self, pull_requests: List[Dict]) -> Dict[str, Any]:
        """Calculate collaboration metrics"""
        if not pull_requests:
            return {}
        
        reviewers = []
        pr_authors = []
        
        for pr in pull_requests:
            author = pr.get("author", {}).get("login")
            if author:
                pr_authors.append(author)
            
            reviews = pr.get("reviews", {}).get("nodes", [])
            for review in reviews:
                reviewer = review.get("author", {}).get("login")
                if reviewer and reviewer != author:
                    reviewers.append(reviewer)
        
        unique_reviewers = len(set(reviewers))
        unique_authors = len(set(pr_authors))
        
        return {
            "unique_reviewers": unique_reviewers,
            "unique_authors": unique_authors,
            "total_reviews": len(reviewers),
            "reviews_per_pr": len(reviewers) / len(pull_requests) if pull_requests else 0,
            "collaboration_index": unique_reviewers * unique_authors
        }
    
    def get_performance_grade(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate performance grade"""
        scores = {}
        max_scores = {}
        
        # DORA Metrics Scoring (40% of total)
        dora_score = 0
        dora_max = 40
        
        lead_time_hours = metrics.get("dora", {}).get("lead_time", {}).get("total_lead_time_hours", 0)
        if lead_time_hours <= self.benchmarks["elite"]["lead_time_hours"]:
            dora_score += 10
        elif lead_time_hours <= self.benchmarks["high"]["lead_time_hours"]:
            dora_score += 8
        elif lead_time_hours <= self.benchmarks["medium"]["lead_time_hours"]:
            dora_score += 6
        else:
            dora_score += 3
        
        deploy_freq = metrics.get("dora", {}).get("deployment_frequency", {}).get("per_week", 0)
        if deploy_freq >= self.benchmarks["elite"]["deployment_frequency_per_week"]:
            dora_score += 10
        elif deploy_freq >= self.benchmarks["high"]["deployment_frequency_per_week"]:
            dora_score += 8
        elif deploy_freq >= self.benchmarks["medium"]["deployment_frequency_per_week"]:
            dora_score += 6
        else:
            dora_score += 3
        
        failure_rate = metrics.get("dora", {}).get("change_failure_rate", {}).get("percentage", 0)
        if failure_rate <= self.benchmarks["elite"]["change_failure_rate"]:
            dora_score += 10
        elif failure_rate <= self.benchmarks["high"]["change_failure_rate"]:
            dora_score += 8
        elif failure_rate <= self.benchmarks["medium"]["change_failure_rate"]:
            dora_score += 6
        else:
            dora_score += 3
        
        mttr_hours = metrics.get("dora", {}).get("mttr", {}).get("mttr_hours", 0)
        if mttr_hours <= self.benchmarks["elite"]["mttr_hours"]:
            dora_score += 10
        elif mttr_hours <= self.benchmarks["high"]["mttr_hours"]:
            dora_score += 8
        elif mttr_hours <= self.benchmarks["medium"]["mttr_hours"]:
            dora_score += 6
        else:
            dora_score += 3
        
        scores["dora"] = dora_score
        max_scores["dora"] = dora_max
        
        # Calculate overall grade
        total_score = sum(scores.values())
        total_max = sum(max_scores.values())
        percentage = (total_score / total_max) * 100 if total_max > 0 else 0
        
        if percentage >= 90:
            grade = "A+"
            grade_description = "Elite Performance"
        elif percentage >= 85:
            grade = "A"
            grade_description = "Excellent Performance"
        elif percentage >= 80:
            grade = "A-"
            grade_description = "Very Good Performance"
        elif percentage >= 75:
            grade = "B+"
            grade_description = "Good Performance"
        elif percentage >= 70:
            grade = "B"
            grade_description = "Above Average Performance"
        else:
            grade = "C"
            grade_description = "Needs Improvement"
        
        return {
            "overall_grade": grade,
            "grade_description": grade_description,
            "percentage": round(percentage, 1),
            "total_score": total_score,
            "max_score": total_max,
            "category_scores": scores,
            "category_max_scores": max_scores
        }
    
    def _parse_date(self, date_str):
        """Parse GitHub date string to datetime object"""
        try:
            if isinstance(date_str, str):
                date_str = date_str.replace("Z", "+00:00")
                
                try:
                    if "." in date_str and "+" in date_str:
                        date_part, tz_part = date_str.rsplit("+", 1)
                        if "." in date_part:
                            base_part, micro_part = date_part.rsplit(".", 1)
                            if len(micro_part) > 6:
                                micro_part = micro_part[:6]
                            elif len(micro_part) < 6:
                                micro_part = micro_part.ljust(6, '0')
                            date_str = f"{base_part}.{micro_part}+{tz_part}"
                    
                    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S.%f%z").replace(tzinfo=None)
                except ValueError:
                    return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z").replace(tzinfo=None)
            return date_str
        except ValueError:
            try:
                return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                logger.warning(f"Failed to parse date: {date_str}")
                return datetime.now()
    
    def _average(self, values: List[float]) -> float:
        """Return the average of a list of values"""
        return float(np.mean(values)) if values else 0.0
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Return the given percentile of a list of values"""
        return float(np.percentile(values, percentile)) if values else 0.0