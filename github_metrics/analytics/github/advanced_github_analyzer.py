"""
Advanced GitHub Analytics Service
Extends basic GitHub operations with advanced analytics and insights
"""
import logging
from typing import Dict, List, Any, Optional
from collections import defaultdict, Counter
from datetime import datetime, timedelta
import statistics

from core.services import GitHubService

logger = logging.getLogger(__name__)


class AdvancedGitHubAnalyzer:
    """
    Advanced GitHub analysis beyond basic API calls
    Focuses on patterns, insights, and advanced metrics
    """
    
    def __init__(self, github_service: GitHubService):
        self.github_service = github_service
    
    def analyze_repository_ecosystem(self, owner: str, repo: str) -> Dict[str, Any]:
        """
        Comprehensive repository ecosystem analysis
        """
        try:
            # Get repository insights
            repo_insights = self.github_service.fetch_repository_insights(owner, repo)
            
            # Get commits and PRs for analysis
            commits = self.github_service.fetch_commits(owner, repo, days_back=90)
            prs = self.github_service.fetch_pull_requests(owner, repo, days_back=90)
            
            analysis = {
                'repository_health': self._analyze_repository_health(repo_insights, commits, prs),
                'contributor_patterns': self._analyze_contributor_patterns(commits, prs),
                'development_velocity': self._analyze_development_velocity(commits, prs),
                'code_quality_indicators': self._analyze_code_quality_patterns(commits, prs),
                'collaboration_network': self._analyze_collaboration_network(prs),
                'release_patterns': self._analyze_release_patterns(repo_insights, commits),
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Repository ecosystem analysis failed: {e}")
            return {'error': str(e)}
    
    def _analyze_repository_health(self, repo_insights: Dict, commits: List, prs: List) -> Dict[str, Any]:
        """Analyze overall repository health indicators"""
        
        # Calculate health score components
        activity_score = min(100, len(commits) * 2 + len(prs) * 5)  # Recent activity
        
        stars = repo_insights.get('stargazerCount', 0)
        forks = repo_insights.get('forkCount', 0)
        popularity_score = min(100, (stars * 0.1) + (forks * 0.5))
        
        # Issue resolution rate
        open_issues = repo_insights.get('openIssues', {}).get('totalCount', 0)
        closed_issues = repo_insights.get('closedIssues', {}).get('totalCount', 0)
        total_issues = open_issues + closed_issues
        
        if total_issues > 0:
            issue_resolution_rate = (closed_issues / total_issues) * 100
        else:
            issue_resolution_rate = 100  # No issues is good
        
        # PR merge rate
        merged_prs = len([pr for pr in prs if pr.get('merged')])
        total_prs = len(prs)
        pr_merge_rate = (merged_prs / total_prs * 100) if total_prs > 0 else 100
        
        # Overall health score
        health_score = (
            activity_score * 0.3 +
            popularity_score * 0.2 +
            issue_resolution_rate * 0.3 +
            pr_merge_rate * 0.2
        )
        
        return {
            'overall_health_score': round(health_score, 2),
            'activity_score': round(activity_score, 2),
            'popularity_score': round(popularity_score, 2),
            'issue_resolution_rate': round(issue_resolution_rate, 2),
            'pr_merge_rate': round(pr_merge_rate, 2),
            'health_indicators': {
                'active_development': activity_score > 50,
                'community_engagement': popularity_score > 30,
                'maintenance_quality': issue_resolution_rate > 70,
                'collaboration_effectiveness': pr_merge_rate > 60
            }
        }
    
    def _analyze_contributor_patterns(self, commits: List, prs: List) -> Dict[str, Any]:
        """Analyze contributor behavior patterns"""
        
        # Contributor commit patterns
        contributor_commits = defaultdict(list)
        contributor_prs = defaultdict(list)
        
        for commit in commits:
            author = commit.get('author', {})
            email = author.get('email', 'unknown')
            if email != 'unknown':
                contributor_commits[email].append(commit)
        
        for pr in prs:
            author = pr.get('author', {})
            login = author.get('login', 'unknown')
            if login != 'unknown':
                contributor_prs[login].append(pr)
        
        # Analyze patterns
        total_contributors = len(set(contributor_commits.keys()))
        active_contributors = len([c for c in contributor_commits.keys() 
                                 if len(contributor_commits[c]) >= 5])
        
        # Contribution distribution (80/20 rule analysis)
        commit_counts = [len(commits) for commits in contributor_commits.values()]
        if commit_counts:
            total_commits = sum(commit_counts)
            commit_counts.sort(reverse=True)
            
            # Top 20% contributors
            top_20_percent_count = max(1, total_contributors // 5)
            top_20_percent_commits = sum(commit_counts[:top_20_percent_count])
            contribution_concentration = (top_20_percent_commits / total_commits * 100) if total_commits > 0 else 0
        else:
            contribution_concentration = 0
        
        return {
            'total_contributors': total_contributors,
            'active_contributors': active_contributors,  # 5+ commits
            'contribution_concentration': round(contribution_concentration, 2),
            'diversity_index': round((active_contributors / max(1, total_contributors)) * 100, 2),
            'top_contributors': [
                {
                    'email': email,
                    'commit_count': len(commits),
                    'avg_commit_size': statistics.mean([
                        c.get('additions', 0) + c.get('deletions', 0) for c in commits
                    ]) if commits else 0
                }
                for email, commits in sorted(contributor_commits.items(), 
                                           key=lambda x: len(x[1]), reverse=True)[:5]
            ]
        }
    
    def _analyze_development_velocity(self, commits: List, prs: List) -> Dict[str, Any]:
        """Analyze development velocity patterns"""
        
        if not commits and not prs:
            return {'error': 'No data available for velocity analysis'}
        
        # Weekly commit patterns
        weekly_commits = defaultdict(int)
        weekly_prs = defaultdict(int)
        
        for commit in commits:
            try:
                date = datetime.strptime(commit['committedDate'], "%Y-%m-%dT%H:%M:%SZ")
                week_key = date.strftime("%Y-W%U")
                weekly_commits[week_key] += 1
            except (ValueError, KeyError):
                continue
        
        for pr in prs:
            try:
                date = datetime.strptime(pr['createdAt'], "%Y-%m-%dT%H:%M:%SZ")
                week_key = date.strftime("%Y-W%U")
                weekly_prs[week_key] += 1
            except (ValueError, KeyError):
                continue
        
        # Calculate velocity metrics
        commit_counts = list(weekly_commits.values())
        pr_counts = list(weekly_prs.values())
        
        avg_commits_per_week = statistics.mean(commit_counts) if commit_counts else 0
        avg_prs_per_week = statistics.mean(pr_counts) if pr_counts else 0
        
        # Velocity consistency (lower std dev = more consistent)
        commit_consistency = 1 / (statistics.stdev(commit_counts) + 1) if len(commit_counts) > 1 else 1
        pr_consistency = 1 / (statistics.stdev(pr_counts) + 1) if len(pr_counts) > 1 else 1
        
        return {
            'avg_commits_per_week': round(avg_commits_per_week, 2),
            'avg_prs_per_week': round(avg_prs_per_week, 2),
            'commit_consistency_score': round(commit_consistency * 100, 2),
            'pr_consistency_score': round(pr_consistency * 100, 2),
            'velocity_trend': self._calculate_trend(commit_counts[-4:]) if len(commit_counts) >= 4 else 'stable',
            'weekly_patterns': {
                'commits': dict(weekly_commits),
                'prs': dict(weekly_prs)
            }
        }
    
    def _analyze_code_quality_patterns(self, commits: List, prs: List) -> Dict[str, Any]:
        """Analyze code quality indicators from commit and PR patterns"""
        
        # Commit message quality analysis
        good_commit_messages = 0
        total_commits = len(commits)
        
        for commit in commits:
            message = commit.get('message', '').lower()
            # Good commit message indicators
            if (len(message) > 10 and 
                any(word in message for word in ['fix', 'add', 'update', 'refactor', 'improve']) and
                not message.startswith('merge')):
                good_commit_messages += 1
        
        commit_message_quality = (good_commit_messages / max(1, total_commits)) * 100
        
        # PR review patterns
        reviewed_prs = sum(1 for pr in prs if pr.get('reviews', {}).get('totalCount', 0) > 0)
        pr_review_rate = (reviewed_prs / max(1, len(prs))) * 100
        
        # Small commit analysis (good practice)
        small_commits = sum(1 for commit in commits 
                          if (commit.get('additions', 0) + commit.get('deletions', 0)) < 100)
        small_commit_rate = (small_commits / max(1, total_commits)) * 100
        
        return {
            'commit_message_quality': round(commit_message_quality, 2),
            'pr_review_rate': round(pr_review_rate, 2),
            'small_commit_rate': round(small_commit_rate, 2),
            'quality_indicators': {
                'good_commit_practices': commit_message_quality > 60,
                'code_review_culture': pr_review_rate > 70,
                'incremental_development': small_commit_rate > 60
            }
        }
    
    def _analyze_collaboration_network(self, prs: List) -> Dict[str, Any]:
        """Analyze collaboration patterns from PRs"""
        
        # Author-reviewer relationships
        collaborations = defaultdict(set)
        reviewer_activity = defaultdict(int)
        
        for pr in prs:
            author = pr.get('author', {}).get('login')
            if not author:
                continue
                
            reviews = pr.get('reviews', {}).get('nodes', [])
            for review in reviews:
                reviewer = review.get('author', {}).get('login')
                if reviewer and reviewer != author:
                    collaborations[author].add(reviewer)
                    reviewer_activity[reviewer] += 1
        
        # Network metrics
        total_authors = len(collaborations)
        total_reviewers = len(reviewer_activity)
        
        # Calculate collaboration density
        possible_connections = total_authors * total_reviewers
        actual_connections = sum(len(reviewers) for reviewers in collaborations.values())
        collaboration_density = (actual_connections / max(1, possible_connections)) * 100
        
        return {
            'total_authors': total_authors,
            'total_reviewers': total_reviewers,
            'collaboration_density': round(collaboration_density, 2),
            'avg_reviewers_per_author': round(actual_connections / max(1, total_authors), 2),
            'top_reviewers': [
                {'reviewer': reviewer, 'review_count': count}
                for reviewer, count in sorted(reviewer_activity.items(), 
                                            key=lambda x: x[1], reverse=True)[:5]
            ]
        }
    
    def _analyze_release_patterns(self, repo_insights: Dict, commits: List) -> Dict[str, Any]:
        """Analyze release and deployment patterns"""
        
        releases = repo_insights.get('releases', {}).get('totalCount', 0)
        
        # Estimate release frequency from commits
        if commits:
            # Group commits by month to estimate release cadence
            monthly_commits = defaultdict(int)
            for commit in commits:
                try:
                    date = datetime.strptime(commit['committedDate'], "%Y-%m-%dT%H:%M:%SZ")
                    month_key = date.strftime("%Y-%m")
                    monthly_commits[month_key] += 1
                except (ValueError, KeyError):
                    continue
            
            # Assume releases happen when there are significant commits
            estimated_release_months = sum(1 for count in monthly_commits.values() if count > 10)
            avg_commits_between_releases = sum(monthly_commits.values()) / max(1, estimated_release_months)
        else:
            estimated_release_months = 0
            avg_commits_between_releases = 0
        
        return {
            'total_releases': releases,
            'estimated_monthly_releases': estimated_release_months,
            'avg_commits_between_releases': round(avg_commits_between_releases, 2),
            'release_frequency_score': min(100, estimated_release_months * 10),  # More frequent = higher score
            'continuous_delivery_indicator': estimated_release_months >= 3  # At least quarterly
        }
    
    def _calculate_trend(self, values: List[float]) -> str:
        """Calculate trend direction from recent values"""
        if len(values) < 2:
            return 'stable'
        
        # Simple linear trend
        recent_avg = statistics.mean(values[-2:])
        earlier_avg = statistics.mean(values[:-2]) if len(values) > 2 else values[0]
        
        if recent_avg > earlier_avg * 1.2:
            return 'increasing'
        elif recent_avg < earlier_avg * 0.8:
            return 'decreasing'
        else:
            return 'stable'