import sys
import json
import random
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
from utls.utls import chunk_loader, find_root_directory


class IssueSelector:

    def __init__(self, chunks_path: str):
        self.issues = []
        self.chunks = chunk_loader(chunks_path=chunks_path)
        for chunk in self.chunks:
            for issue in chunk:
                self.issues.append(issue)

    def random_select_issues(
            self,
            issues: List[Dict[str, Any]],
            num_issues: Optional[int] = 12,
            seed: Optional[int] = 12345
    ) -> List[Dict[str, Any]]:
        """
        Randomly select a specified number of issues from all chunks.
        """
        # Validate input
        if num_issues < 1:
            raise ValueError("num_issues must be at least 1")

        # Set random seed if provided
        if seed is not None:
            random.seed(seed)
            used_seed = seed
        else:
            # Use current timestamp as seed for true randomness
            used_seed = int(datetime.now().timestamp() * 1000000)
            random.seed(used_seed)

        total_available = len(issues)
        print(f"Total issues available: {total_available}")

        # Validate requested amount
        if num_issues > total_available:
            raise ValueError(
                f"Requested {num_issues} issues, but only {total_available} available. "
                f"Please request a number between 1 and {total_available}."
            )

        # Randomly select issues
        print(f"Randomly selecting {num_issues} issues...")
        return random.sample(issues, num_issues)

    def select_issues_by_time(self) -> Dict[str, List[Dict[str, Any]]]:
        """
        Group issues by year. Returns a dict of year -> list of issues.
        """
        issues = self.issues
        result = {str(y): [] for y in range(2018, 2026)}
        for issue in issues:
            created_at = issue.get("created_at")
            if not created_at:
                continue
            try:
                year = datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                ).year
            except (ValueError, TypeError):
                year = int(created_at[:4]) if isinstance(created_at, str) and len(created_at) >= 4 else None
            if year is not None and 2018 <= year <= 2025:
                result[str(year)].append(issue)
        return result



    def select_issues_by_state(
            self,
            issues: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Select issue by state, including open or closed.
        """
        states = ['open', 'closed']
        result = {}
        for state in states:
            filtered = [i for i in issues if (i.get("state") or "").lower() == (state or "").lower()]
            result[state] = filtered
        return result

    def select_issues_by_comments(
        self,
        issues: List[Dict[str, Any]],
        top_number: Optional[int] = 8
    ) -> List[Dict[str, Any]]:
        """
        Select issues with most comments.
        """
        sorted_issues = sorted(
            issues,
            key=lambda i: i.get("comments", 0),
            reverse=True
        )
        return sorted_issues[: top_number] if top_number is not None else sorted_issues

    def handle(self):
        issues_by_time = self.select_issues_by_time()
        for y in range(2021, 2025):
            selected_year = str(y)
            selected_issues = issues_by_time[selected_year]
            issue_by_state = self.select_issues_by_state(selected_issues)
            issue_open = issue_by_state['open']
            issue_closed = issue_by_state['closed']
            issue_open_by_comments = self.select_issues_by_comments(issue_open)
            issue_closed_by_comments = self.select_issues_by_comments(issue_closed)
            top_open_ids = {i.get("id") for i in issue_open_by_comments}
            issue_open = [i for i in issue_open if i.get("id") not in top_open_ids]
            top_closed_ids = {i.get("id") for i in issue_closed_by_comments}
            issue_closed = [i for i in issue_closed if i.get("id") not in top_closed_ids]
            random_open_issues = self.random_select_issues(issue_open)
            random_closed_issues = self.random_select_issues(issue_closed)
            chunk_data = issue_open_by_comments + issue_closed_by_comments + random_open_issues + random_closed_issues
            root_dir = find_root_directory()
            filename = f"{selected_year}.json"
            file_path = root_dir / "data/issue_filtered_selected" / filename
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(chunk_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                raise OSError(f"Failed to write file {file_path}: {e}")





if __name__ == "__main__":
    selector = IssueSelector("data/issue_filtered")
    # selector.handle()
    issues_by_time = selector.select_issues_by_time()
    for y in range(2021, 2026):
        selected_year = str(y)
        selected_issues = issues_by_time[selected_year]
        root_dir = find_root_directory()
        filename = f"{selected_year}.json"
        file_path = root_dir / "data/issue_filtered_selected" / filename
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(selected_issues, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise OSError(f"Failed to write file {file_path}: {e}")
