from typing import List, Dict, Any, Optional
import json
import random
from datetime import datetime


from utls.utls import chunk_loader, find_root_directory


class CompatibilityReportSelector:

    def __init__(self, chunks_path: str):
        self.issues = []
        self.chunks = chunk_loader(chunks_path=chunks_path)
        for chunk in self.chunks:
            for issue in chunk:
                self.issues.append(issue)
        self.compatibility_report = []


    def select_report_by_order(self) -> List[Dict[str, Any]]:
        """
        Select the first compatibility reports for each issue.

        Return:
            [
                {
                    "issue_number": [int],
                    "first_compatibility_report": [str]
                },
                ...
            ]
        """
        result = []
        marker = "# Compatibility Report"
        for issue in self.issues:
            reports_in_order = {}
            body = issue.get("body") or ""
            if marker in body:
                reports_in_order["issue_number"] = issue.get("number")
                reports_in_order["first_compatibility_report"] = body
                result.append(reports_in_order)
                continue
            for comment in issue.get("comments_data") or []:
                comment_body = comment.get("body") or ""
                if marker in comment_body:
                    reports_in_order["issue_number"] = issue.get("number")
                    reports_in_order["first_compatibility_report"] = comment_body
                    result.append(reports_in_order)
                    break

        return result

    def collect_all_reports(self) -> List[Dict[str, Any]]:
        """
        Collect all compatibility reports. The compatibility report needs to have following 'non-report' comments.
        """
        result = []
        marker = "# Compatibility Report"
        for issue in self.issues:
            issue_number = issue.get("number")
            issue_title = issue.get("title")
            issue_id = issue.get("id")
            body = issue.get("body") or ""
            comments_list = issue.get("comments_data") or []
            if marker in body:
                has_subsequent_non_report = any(
                    marker not in (c.get("body") or "")
                    for c in comments_list
                )
                if comments_list and has_subsequent_non_report:
                    result.append({"issue_number": issue_number,
                               "issue_title": issue_title,
                               "id": issue_id,
                               "compatibility_report": body})
            for idx, comment in enumerate(comments_list):
                comment_body = comment.get("body") or ""
                comment_id = comment.get("id")
                if marker in comment_body:
                    subsequent = comments_list[idx + 1:]
                    has_subsequent_non_report = any(
                        marker not in (c.get("body") or "")
                        for c in subsequent
                    )
                    if subsequent and has_subsequent_non_report:
                        result.append({"issue_number": issue_number,
                                   "issue_title": issue_title,
                                   "id": comment_id,
                                   "compatibility_report": comment_body})
        self.compatibility_report = result
        return result


    def calculate_report_num(self):
        """
        Calculate selected report number.
        """
        report_num = 0
        for issue in self.issues:
            if '# Compatibility Report' in issue.get('body'):
                report_num += 1
            for comment in issue.get('comments_data'):
                if '# Compatibility Report' in comment.get('body'):
                    report_num += 1
        return report_num

    def random_sampling(self,
                        num: Optional[int] = 330,
                        seed: Optional[int] = 12345
    ) -> List[Dict[str, Any]]:
        """
        Random sampling compatibility report.
        """
        # Validate input
        if num < 1:
            raise ValueError("sampling number must be at least 1")

        # Set random seed if provided
        if seed is not None:
            random.seed(seed)
            used_seed = seed
        else:
            # Use current timestamp as seed for true randomness
            used_seed = int(datetime.now().timestamp() * 1000000)
            random.seed(used_seed)

        total_available = len(self.compatibility_report)
        print(f"Total issues available: {total_available}")

        # Validate requested amount
        if num > total_available:
            raise ValueError(
                f"Requested {num} issues, but only {total_available} available. "
                f"Please request a number between 1 and {total_available}."
            )

        # Randomly select issues
        print(f"Randomly selecting {num} issues...")
        return random.sample(self.compatibility_report, num)

    def handler(self):
        # first_report_per_issue = self.select_report_by_order()
        root_dir = find_root_directory()
        # filename = "first_report_per_issue.json"
        # file_path = root_dir / "data/compatibility_report_selection" / filename
        # try:
        #     with open(file_path, 'w', encoding='utf-8') as f:
        #         json.dump(first_report_per_issue, f, ensure_ascii=False, indent=2)
        # except Exception as e:
        #     raise OSError(f"Failed to write file {file_path}: {e}")
        all_reports = self.collect_all_reports()
        # all_report_discussion_pair = self.collect_report_discussion_pair()
        all_reports_path = root_dir / "data/compatibility_report_selection" / "all_report.json"
        try:
            all_reports_path.parent.mkdir(parents=True, exist_ok=True)
            with open(all_reports_path, 'w', encoding='utf-8') as f:
                json.dump(all_reports, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise OSError(f"Failed to write file {all_reports_path}: {e}")
        # Random sampling
        random_sampling_reports = self.random_sampling()
        random_sampling_reports_path = root_dir / "data/compatibility_report_selection" / "random_sampling_report.json"

        try:
            random_sampling_reports_path.parent.mkdir(parents=True, exist_ok=True)
            with open(random_sampling_reports_path, 'w', encoding='utf-8') as f:
                json.dump(random_sampling_reports, f, ensure_ascii=False, indent=2)
        except Exception as e:
            raise OSError(f"Failed to write file {random_sampling_reports_path}: {e}")



if __name__ == "__main__":
    selector = CompatibilityReportSelector("data/issue_filtered_selected")
    selector.calculate_report_num()
    selector.handler()