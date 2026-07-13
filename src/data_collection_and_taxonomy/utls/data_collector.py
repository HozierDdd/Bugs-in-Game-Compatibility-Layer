#!/usr/bin/env python3
"""
GitHub Issue Data Collector for ValveSoftware/proton repository

This script collects issue data from the ValveSoftware/proton GitHub repository
and saves it to JSON files.

Usage:
    python data_collector.py [--state STATE] [--max-issues MAX] [--output-dir DIR] [--token TOKEN]
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class GitHubIssueCollector:
    """Collects issue data from GitHub repositories."""
    
    BASE_URL = "https://api.github.com"
    REPO_OWNER = "ValveSoftware"
    REPO_NAME = "proton"
    
    def __init__(self, token: Optional[str] = None, output_dir: str = "data/issue_origin"):
        """
        Initialize the collector.
        
        Args:
            token: GitHub personal access token (optional, but recommended for higher rate limits)
            output_dir: Directory to save collected data
        """
        self.token = token
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Proton-Parser/1.0"
        }
        if token:
            self.headers["Authorization"] = f"token {token}"
    
    def _check_rate_limit(self) -> tuple[int, int, int]:
        """
        Check current rate limit status.
        
        Returns:
            Tuple of (remaining, limit, reset_time)
        """
        url = f"{self.BASE_URL}/rate_limit"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                core = data.get("resources", {}).get("core", {})
                return (
                    core.get("remaining", 0),
                    core.get("limit", 60),
                    core.get("reset", 0)
                )
        except:
            pass
        return (0, 60, 0)
    
    def _wait_for_rate_limit(self):
        """Wait if rate limit is exhausted."""
        remaining, limit, reset_time = self._check_rate_limit()
        
        if remaining == 0:
            wait_time = max(0, reset_time - time.time())
            if wait_time > 0:
                print(f"\n⚠️  Rate limit exhausted ({limit}/{limit} used). Waiting {wait_time:.0f} seconds until reset...")
                time.sleep(wait_time + 1)
                # Re-check after waiting
                remaining, limit, _ = self._check_rate_limit()
                print(f"✅ Rate limit reset. Remaining: {remaining}/{limit}")
    
    def _make_request(self, url: str, params: Optional[Dict] = None) -> requests.Response:
        """
        Make a GitHub API request with rate limit handling.
        
        Args:
            url: API endpoint URL
            params: Query parameters
            
        Returns:
            Response object
        """
        while True:
            # Check rate limit before making request
            remaining, limit, _ = self._check_rate_limit()
            if remaining == 0:
                self._wait_for_rate_limit()
            
            response = requests.get(url, headers=self.headers, params=params)
            
            # Handle rate limiting (backup check)
            if response.status_code == 403 and "rate limit" in response.text.lower():
                reset_time = int(response.headers.get("X-RateLimit-Reset", time.time() + 60))
                wait_time = max(0, reset_time - time.time())
                print(f"\n⚠️  Rate limit exceeded. Waiting {wait_time:.0f} seconds...")
                time.sleep(wait_time + 1)
                continue
            
            # Handle other errors
            if response.status_code == 404:
                raise ValueError(f"Resource not found: {url}")
            elif response.status_code != 200:
                response.raise_for_status()
            
            return response
    
    def get_issues(self, state: str = "all", max_issues: Optional[int] = None,
                   per_page: int = 100) -> List[Dict]:
        """
        Collect issues from the repository.
        
        Args:
            state: Issue state ('open', 'closed', or 'all')
            max_issues: Maximum number of issues to collect (None for all)
            per_page: Number of issues per page (max 100)
            
        Returns:
            List of issue dictionaries
        """
        issues = []
        page = 1
        url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/issues"
        
        print(f"Collecting {state} issues from {self.REPO_OWNER}/{self.REPO_NAME}...")
        
        while True:
            params = {
                "state": state,
                "page": page,
                "per_page": min(per_page, 100),
                "direction": "asc"  # Start from oldest issues
            }
            
            print(f"Fetching page {page}...", end=" ")
            response = self._make_request(url, params=params)
            page_issues = response.json()
            
            # Handle empty page
            if not page_issues:
                print("No more issues.")
                break
            
            issues.extend(page_issues)
            print(f"Found {len(page_issues)} issues (total: {len(issues)})")
            
            # Check if we've reached the limit
            if max_issues and len(issues) >= max_issues:
                issues = issues[:max_issues]
                break
            
            # Check if there's a next page
            if "next" not in response.links:
                break
            
            page += 1
            
            # Be respectful to GitHub API
            time.sleep(0.5)
        
        print(f"\nCollected {len(issues)} issues total.")
        return issues
    
    def get_issue_comments(self, issue_number: int) -> List[Dict]:
        """
        Get comments for a specific issue.
        
        Args:
            issue_number: Issue number
            
        Returns:
            List of comment dictionaries
        """
        comments = []
        page = 1
        url = f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}/issues/{issue_number}/comments"
        
        while True:
            params = {
                "page": page,
                "per_page": 100
            }
            
            response = self._make_request(url, params=params)
            page_comments = response.json()
            
            if not page_comments:
                break
            
            comments.extend(page_comments)
            
            if "next" not in response.links:
                break
            
            page += 1
            time.sleep(0.5)  # Small delay between paginated comment requests
        
        return comments
    
    def enrich_issues(self, issues: List[Dict], include_comments: bool = True,
                     progress_file: Optional[str] = None) -> List[Dict]:
        """
        Enrich issues with additional data like comments.
        
        Args:
            issues: List of issue dictionaries
            include_comments: Whether to fetch comments for each issue
            progress_file: Optional file to save progress (for resume capability)
            
        Returns:
            Enriched list of issues
        """
        # Load progress if resuming
        processed_numbers = set()
        if progress_file and Path(progress_file).exists():
            try:
                with open(progress_file, "r") as f:
                    progress_data = json.load(f)
                    processed_numbers = set(progress_data.get("processed", []))
                    print(f"📋 Resuming from progress file. Already processed {len(processed_numbers)} issues.")
            except:
                pass
        
        enriched = []
        remaining, limit, _ = self._check_rate_limit()
        
        for i, issue in enumerate(issues, 1):
            issue_number = issue["number"]
            
            # Skip if already processed
            if issue_number in processed_numbers:
                enriched_issue = issue.copy()
                enriched_issue["comments_data"] = []  # Will be skipped anyway
                enriched.append(enriched_issue)
                continue
            
            # Show rate limit status periodically
            if i % 10 == 1:
                remaining, limit, _ = self._check_rate_limit()
                print(f"\n📊 Rate limit: {remaining}/{limit} remaining")
            
            print(f"Enriching issue #{issue_number} ({i}/{len(issues)})...", end=" ")
            
            enriched_issue = issue.copy()
            
            if include_comments:
                enriched_issue["comments_data"] = self.get_issue_comments(issue_number)
                print(f"Found {len(enriched_issue['comments_data'])} comments")
            else:
                print("Skipped comments")
            
            enriched.append(enriched_issue)
            
            # Save progress periodically
            if progress_file and i % 5 == 0:
                processed_numbers.add(issue_number)
                try:
                    with open(progress_file, "w") as f:
                        json.dump({"processed": list(processed_numbers)}, f)
                except:
                    pass
            
            # Longer delay between comment requests to avoid rate limits
            if include_comments:
                time.sleep(1.0)  # Increased from 0.3 to 1.0 seconds
        
        # Clean up progress file
        if progress_file and Path(progress_file).exists():
            try:
                Path(progress_file).unlink()
            except:
                pass
        
        return enriched
    
    def save_issues(self, issues: List[Dict], filename: Optional[str] = None):
        """
        Save issues to a JSON file.
        
        Args:
            issues: List of issue dictionaries
            filename: Output filename (auto-generated if None)
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"proton_issues_{timestamp}.json"
        
        output_path = self.output_dir / filename
        
        output_data = {
            "metadata": {
                "repository": f"{self.REPO_OWNER}/{self.REPO_NAME}",
                "collection_date": datetime.now().isoformat(),
                "total_issues": len(issues),
                "api_url": f"{self.BASE_URL}/repos/{self.REPO_OWNER}/{self.REPO_NAME}"
            },
            "issues": issues
        }
        
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved {len(issues)} issues to {output_path}")
        print(f"File size: {output_path.stat().st_size / 1024 / 1024:.2f} MB")
    
    def collect(self, state: str = "all", max_issues: Optional[int] = None,
                include_comments: bool = True, filename: Optional[str] = None,
                save_progress: bool = True):
        """
        Main method to collect and save issues.
        
        Args:
            state: Issue state ('open', 'closed', or 'all')
            max_issues: Maximum number of issues to collect
            include_comments: Whether to fetch comments for each issue
            filename: Output filename (auto-generated if None)
            save_progress: Whether to save progress for resume capability
        """
        # Collect issues
        issues = self.get_issues(state=state, max_issues=max_issues)
        
        # Enrich with comments if requested
        progress_file = None
        if include_comments and issues:
            print("\nEnriching issues with comments...")
            if save_progress:
                progress_file = str(self.output_dir / ".progress.json")
            issues = self.enrich_issues(issues, include_comments=include_comments,
                                       progress_file=progress_file)
        
        # Save to file
        if issues:
            self.save_issues(issues, filename=filename)
        else:
            print("No issues to save.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Collect issue data from ValveSoftware/proton GitHub repository"
    )
    parser.add_argument(
        "--state",
        choices=["open", "closed", "all"],
        default="all",
        help="Issue state to collect (default: all)"
    )
    parser.add_argument(
        "--max-issues",
        type=int,
        default=None,
        help="Maximum number of issues to collect (default: all)"
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="data/issue_origin",
        help="Output directory for collected data (default: data/issue_origin)"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="GitHub personal access token (optional but recommended)"
    )
    parser.add_argument(
        "--no-comments",
        action="store_true",
        help="Skip collecting comments (faster)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output filename (default: auto-generated with timestamp)"
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress saving (resume capability)"
    )
    
    args = parser.parse_args()
    
    # Try to get token from environment if not provided
    token = args.token or os.getenv("GITHUB_TOKEN")
    
    # Initialize collector
    collector = GitHubIssueCollector(token=token, output_dir=args.output_dir)
    
    # Collect issues
    try:
        collector.collect(
            state=args.state,
            max_issues=args.max_issues,
            include_comments=not args.no_comments,
            filename=args.output,
            save_progress=not args.no_progress
        )
    except KeyboardInterrupt:
        print("\n\nCollection interrupted by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
