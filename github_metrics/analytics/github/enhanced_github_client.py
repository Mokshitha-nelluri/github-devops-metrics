"""
Enhanced GitHub API client with GraphQL support
Migrated from backend/github_api.py - Advanced functionality
"""
import requests
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from django.core.cache import cache
from analytics.constants import GITHUB_GRAPHQL_URL, GITHUB_API_BASE_URL

logger = logging.getLogger(__name__)


class EnhancedGitHubClient:
    """Enhanced GitHub API with GraphQL support and advanced features"""
    
    def __init__(self, token: str):
        self.api_url = GITHUB_GRAPHQL_URL
        self.rest_url = GITHUB_API_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    def execute_query(self, query: str, variables: Optional[dict] = None, retries: int = 3, backoff_factor: int = 2) -> Optional[dict]:
        """Executes a GraphQL query with enhanced retry logic and rate limit handling."""
        attempt = 0
        while attempt < retries:
            try:
                response = requests.post(
                    self.api_url,
                    json={"query": query, "variables": variables or {}},
                    headers=self.headers
                )
                
                # Handle rate limiting (429 or secondary 403)
                if response.status_code == 429 or (response.status_code == 403 and "rate limit" in response.text.lower()):
                    reset_time = int(response.headers.get('X-RateLimit-Reset', time.time() + 60))
                    sleep_time = max(reset_time - int(time.time()), 60)
                    logger.warning(f"Rate limited. Sleeping for {sleep_time} seconds...")
                    time.sleep(sleep_time)
                    continue
                
                response.raise_for_status()
                data = response.json()
                
                if "errors" in data:
                    error_messages = [e.get("message", "Unknown error") for e in data["errors"]]
                    logger.error(f"GraphQL errors: {', '.join(error_messages)}")
                    raise ValueError(f"GraphQL errors: {', '.join(error_messages)}")
                
                return data
                
            except (requests.exceptions.RequestException, ValueError) as e:
                attempt += 1
                wait_time = backoff_factor ** attempt
                logger.warning(f"Attempt {attempt} failed: {e}. Retrying in {wait_time}s...")
                if attempt < retries:
                    time.sleep(wait_time)
        
        logger.error("All retries failed.")
        return None
    
    def get_authenticated_user(self) -> Optional[Dict[str, Any]]:
        """Get the authenticated user's profile information."""
        query = """
        query {
            viewer {
                login
                name
                email
                avatarUrl
                createdAt
                bio
                company
                location
                publicRepos: repositories(privacy: PUBLIC) {
                    totalCount
                }
                privateRepos: repositories(privacy: PRIVATE) {
                    totalCount
                }
                contributionsCollection {
                    totalCommitContributions
                    totalPullRequestContributions
                    totalRepositoriesWithContributedCommits
                }
                followers {
                    totalCount
                }
                following {
                    totalCount
                }
            }
        }
        """
        
        data = self.execute_query(query)
        if data:
            return data.get("data", {}).get("viewer")
        return None
    
    def fetch_user_repositories(self, username: Optional[str] = None, limit: int = 200, include_private: bool = True) -> List[Dict[str, Any]]:
        """Fetch ALL user's repositories using enhanced discovery methods."""
        
        if username:
            # For specific users, use simpler approach (public repos only)
            return self._fetch_public_user_repos(username, limit)
        
        # For authenticated user, use comprehensive discovery
        logger.info("🔍 Using enhanced repository discovery for authenticated user...")
        
        try:
            return self._fetch_basic_user_repos(include_private, limit)
            
        except Exception as e:
            logger.warning(f"Enhanced discovery failed, falling back to basic method: {e}")
            return self._fetch_basic_user_repos(include_private, limit)
    
    def _fetch_public_user_repos(self, username: str, limit: int) -> List[Dict[str, Any]]:
        """Fetch public repositories for a specific user."""
        query = """
        query($username: String!, $first: Int!, $cursor: String) {
            user(login: $username) {
                repositories(
                    first: $first,
                    after: $cursor,
                    orderBy: {field: UPDATED_AT, direction: DESC}
                    privacy: PUBLIC
                ) {
                    nodes {
                        name
                        owner {
                            login
                        }
                        isPrivate
                        updatedAt
                        createdAt
                        description
                        primaryLanguage {
                            name
                        }
                        stargazerCount
                        forkCount
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
        """
        
        all_repos = []
        variables = {"username": username, "first": min(limit, 100), "cursor": None}
        max_pages = 10
        page_count = 0
        
        while page_count < max_pages:
            data = self.execute_query(query, variables)
            if not data:
                break
            
            repos = data.get("data", {}).get("user", {}).get("repositories", {}).get("nodes", [])
            page_info = data.get("data", {}).get("user", {}).get("repositories", {}).get("pageInfo", {})
            
            if not repos:
                break
                
            all_repos.extend(repos)
            page_count += 1
            
            if not page_info.get("hasNextPage"):
                break
                
            variables["cursor"] = page_info["endCursor"]
        
        return all_repos
    
    def _fetch_basic_user_repos(self, include_private: bool, limit: int) -> List[Dict[str, Any]]:
        """Basic fallback method for fetching user repositories."""
        privacy_filter = "" if include_private else "privacy: PUBLIC"
        query = f"""
        query($first: Int!, $cursor: String) {{
            viewer {{
                repositories(
                    first: $first,
                    after: $cursor,
                    orderBy: {{field: UPDATED_AT, direction: DESC}}
                    {privacy_filter}
                ) {{
                    nodes {{
                        name
                        owner {{
                            login
                        }}
                        isPrivate
                        updatedAt
                        createdAt
                        description
                        primaryLanguage {{
                            name
                        }}
                        stargazerCount
                        forkCount
                    }}
                    pageInfo {{
                        hasNextPage
                        endCursor
                    }}
                }}
            }}
        }}
        """
        
        all_repos = []
        variables = {"first": min(limit, 100), "cursor": None}
        max_pages = 10
        page_count = 0
        
        while page_count < max_pages:
            data = self.execute_query(query, variables)
            if not data:
                break
            
            repos = data.get("data", {}).get("viewer", {}).get("repositories", {}).get("nodes", [])
            page_info = data.get("data", {}).get("viewer", {}).get("repositories", {}).get("pageInfo", {})
            
            if not repos:
                break
                
            all_repos.extend(repos)
            page_count += 1
            
            if not page_info.get("hasNextPage"):
                break
                
            variables["cursor"] = page_info["endCursor"]
        
        logger.info(f"Basic method found {len(all_repos)} repositories")
        return all_repos
        
    def fetch_commits(self, owner: str, repo: str, developer_email: Optional[str] = None, days_back: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetches ALL commits from repository history with advanced options."""
        
        # Only apply time filter if explicitly requested
        since_clause = ""
        variables_base = {
            "owner": owner,
            "repo": repo,
            "cursor": None
        }
        
        if days_back is not None:
            since_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%dT%H:%M:%SZ')
            since_clause = ", since: $since"
            variables_base["since"] = since_date
        
        if developer_email:
            query = f"""
            query ($owner: String!, $repo: String!, $cursor: String{"" if days_back is None else ", $since: GitTimestamp!"}, $author_email: String!) {{
                repository(owner: $owner, name: $repo) {{
                    defaultBranchRef {{
                        target {{
                            ... on Commit {{
                                history(first: 100, after: $cursor{since_clause}, author: {{emails: [$author_email]}}) {{
                                    nodes {{
                                        oid
                                        committedDate
                                        additions
                                        deletions
                                        changedFiles
                                        author {{
                                            email
                                            name
                                            date
                                        }}
                                        committer {{
                                            email
                                            name
                                            date
                                        }}
                                        message
                                        messageHeadline
                                        messageBody
                                    }}
                                    pageInfo {{
                                        hasNextPage
                                        endCursor
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
            variables_base["author_email"] = developer_email
        else:
            query = f"""
            query ($owner: String!, $repo: String!, $cursor: String{"" if days_back is None else ", $since: GitTimestamp!"}) {{
                repository(owner: $owner, name: $repo) {{
                    defaultBranchRef {{
                        target {{
                            ... on Commit {{
                                history(first: 100, after: $cursor{since_clause}) {{
                                    nodes {{
                                        oid
                                        committedDate
                                        additions
                                        deletions
                                        changedFiles
                                        author {{
                                            email
                                            name
                                            date
                                        }}
                                        committer {{
                                            email
                                            name
                                            date
                                        }}
                                        message
                                        messageHeadline
                                        messageBody
                                    }}
                                    pageInfo {{
                                        hasNextPage
                                        endCursor
                                    }}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            """
        
        variables = variables_base
        
        commits = []
        max_pages = 50  # Increased to get complete commit history
        page_count = 0
        
        while page_count < max_pages:
            data = self.execute_query(query, variables)
            if not data:
                break
            
            history = data.get("data", {}).get("repository", {}).get("defaultBranchRef", {}).get("target", {}).get("history", {})
            if not history:
                break
            
            new_commits = history.get("nodes", [])
            if not new_commits:  # No more commits
                break
                
            commits.extend(new_commits)
            
            page_info = history.get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
                
            variables["cursor"] = page_info["endCursor"]
            page_count += 1
        
        logger.info(f"Fetched {len(commits)} commits for {owner}/{repo} ({'all-time' if days_back is None else f'{days_back} days'})")
        return commits
    
    def fetch_pull_requests(self, owner: str, repo: str, developer_email: Optional[str] = None, days_back: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetches ALL PRs from repository history with detailed information."""
        
        query = """
        query ($owner: String!, $repo: String!, $cursor: String) {
            repository(owner: $owner, name: $repo) {
                pullRequests(first: 100, after: $cursor, states: [MERGED, CLOSED, OPEN], orderBy: {field: UPDATED_AT, direction: DESC}) {
                    nodes {
                        number
                        title
                        body
                        createdAt
                        mergedAt
                        closedAt
                        updatedAt
                        state
                        author {
                            login
                            ... on User {
                                email
                            }
                        }
                        mergeable
                        merged
                        additions
                        deletions
                        changedFiles
                        commits(first: 100) {
                            totalCount
                            nodes {
                                commit {
                                    committedDate
                                    additions
                                    deletions
                                    changedFiles
                                    author {
                                        email
                                        name
                                    }
                                    message
                                }
                            }
                        }
                        reviews(first: 20) {
                            totalCount
                            nodes {
                                author {
                                    login
                                }
                                submittedAt
                                state
                                body
                            }
                        }
                        reviewRequests(first: 10) {
                            nodes {
                                requestedReviewer {
                                    ... on User {
                                        login
                                    }
                                }
                            }
                        }
                        labels(first: 10) {
                            nodes {
                                name
                                color
                            }
                        }
                        assignees(first: 5) {
                            nodes {
                                login
                            }
                        }
                        milestone {
                            title
                            dueOn
                            state
                        }
                    }
                    pageInfo {
                        hasNextPage
                        endCursor
                    }
                }
            }
        }
        """
        
        variables = {"owner": owner, "repo": repo, "cursor": None}
        all_prs = []
        max_pages = 20  # Increased to get complete PR history
        page_count = 0
        
        while page_count < max_pages:
            data = self.execute_query(query, variables)
            if not data:
                break
            
            prs = data.get("data", {}).get("repository", {}).get("pullRequests", {}).get("nodes", [])
            if not prs:  # No more PRs
                break
            
            # Filter by developer email if provided, but no time filtering by default
            filtered_prs = []
            for pr in prs:
                # Apply time filter only if days_back is specified
                if days_back is not None:
                    if pr.get("updatedAt"):
                        updated_date = datetime.strptime(pr["updatedAt"], "%Y-%m-%dT%H:%M:%SZ")
                        cutoff_date = datetime.now() - timedelta(days=days_back)
                        if updated_date < cutoff_date:
                            continue
                
                # Filter by email if provided
                if developer_email:
                    has_user_commits = any(
                        commit.get("commit", {}).get("author", {}).get("email") == developer_email
                        for commit in pr.get("commits", {}).get("nodes", [])
                    )
                    if has_user_commits:
                        filtered_prs.append(pr)
                else:
                    filtered_prs.append(pr)
            
            all_prs.extend(filtered_prs)
            
            page_info = data.get("data", {}).get("repository", {}).get("pullRequests", {}).get("pageInfo", {})
            if not page_info.get("hasNextPage"):
                break
                
            variables["cursor"] = page_info["endCursor"]
            page_count += 1
        
        logger.info(f"Fetched {len(all_prs)} PRs for {owner}/{repo} ({'all-time' if days_back is None else f'{days_back} days'})")
        return all_prs
    
    def fetch_repository_insights(self, owner: str, repo: str) -> Dict[str, Any]:
        """Fetch comprehensive repository insights and metadata."""
        query = """
        query($owner: String!, $repo: String!) {
            repository(owner: $owner, name: $repo) {
                id
                name
                owner {
                    login
                }
                isPrivate
                description
                url
                createdAt
                updatedAt
                pushedAt
                homepageUrl
                stargazerCount
                forkCount
                watcherCount: watchers {
                    totalCount
                }
                openIssues: issues(states: OPEN) {
                    totalCount
                }
                closedIssues: issues(states: CLOSED) {
                    totalCount
                }
                pullRequests(states: OPEN) {
                    totalCount
                }
                pullRequestsMerged: pullRequests(states: MERGED) {
                    totalCount
                }
                primaryLanguage {
                    name
                    color
                }
                languages(first: 5) {
                    nodes {
                        name
                    }
                }
                licenseInfo {
                    name
                    spdxId
                }
                repositoryTopics(first: 10) {
                    nodes {
                        topic {
                            name
                        }
                    }
                }
                defaultBranchRef {
                    name
                    target {
                        ... on Commit {
                            history {
                                totalCount
                            }
                        }
                    }
                }
                diskUsage
                codeOfConduct {
                    name
                }
                releases(first: 1, orderBy: {field: CREATED_AT, direction: DESC}) {
                    totalCount
                    nodes {
                        name
                        tagName
                        createdAt
                    }
                }
            }
        }
        """
        
        data = self.execute_query(query, {"owner": owner, "repo": repo})
        if data:
            return data.get("data", {}).get("repository", {})
        return {}
    
    def setup_repository_webhook(self, owner: str, repo: str, webhook_url: str) -> Optional[Dict[str, Any]]:
        """Set up repository webhook for real-time updates."""
        url = f"{self.rest_url}/repos/{owner}/{repo}/hooks"
        payload = {
            "name": "web",
            "active": True,
            "events": ["push", "pull_request", "release"],
            "config": {
                "url": webhook_url,
                "content_type": "json"
            }
        }
        
        try:
            response = requests.post(url, json=payload, headers=self.headers)
            response.raise_for_status()
            logger.info(f"Webhook created for {owner}/{repo} at {webhook_url}")
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Webhook creation failed: {str(e)}")
            return None
    
    def fetch_global_user_activity(self, user_email: str, months_back: int = 6) -> Dict[str, Any]:
        """Fetch global user activity across all accessible repositories"""
        try:
            # Calculate date range
            end_date = datetime.now()
            start_date = end_date - timedelta(days=months_back * 30)
            
            # First, get user info to extract username
            user_info = self.get_authenticated_user()
            if not user_info:
                return {"error": "Failed to get user info"}
            
            username = user_info.get("login")
            if not username:
                return {"error": "Failed to get username"}
            
            # Get user repositories
            repositories = self.fetch_user_repositories(username, limit=50)
            if not repositories:
                return {"error": "No repositories found"}
            
            all_commits = []
            all_prs = []
            
            # Fetch data from each repository
            for repo in repositories:
                owner = "unknown"
                name = "unknown"
                try:
                    owner = repo.get("owner", {}).get("login", "")
                    name = repo.get("name", "")
                    
                    if not owner or not name:
                        continue
                    
                    # Fetch commits for this repo
                    repo_commits = self.fetch_commits(owner, name, developer_email=user_email, days_back=months_back * 30)
                    if repo_commits:
                        # Add repository info to each commit
                        for commit in repo_commits:
                            commit["repository"] = f"{owner}/{name}"
                        all_commits.extend(repo_commits)
                    
                    # Fetch PRs for this repo
                    repo_prs = self.fetch_pull_requests(owner, name, user_email, days_back=months_back * 30)
                    if repo_prs:
                        # Add repository info to each PR
                        for pr in repo_prs:
                            pr["repository"] = f"{owner}/{name}"
                        all_prs.extend(repo_prs)
                        
                except Exception as e:
                    logger.warning(f"Failed to fetch data for {owner}/{name}: {str(e)}")
                    continue
            
            return {
                "commits": all_commits,
                "pull_requests": all_prs,
                "repositories": repositories,
                "user_info": user_info,
                "date_range": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Error fetching global user activity: {str(e)}")
            return {"error": str(e)}
    
    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """Get authenticated user information using REST API"""
        try:
            url = f"{self.rest_url}/user"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching user info: {str(e)}")
            return None