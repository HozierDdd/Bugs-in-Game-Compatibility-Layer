from utls.utls import chunk_loader, chunk_divider


class DataFilter:
    """
    Filter rules:
    1. Ignore issues closed by following reasons <state_reason>: 1) not_planned; 2) duplicate;
    2. Ignore issues without any comments.
    3. Ignore issues and the following discussions without formal compatibility reports.
    """

    def __init__(self):
        self.data = chunk_loader()

    def _has_formal_compatibility_report(self, issue: dict) -> bool:
        body = (issue.get("body") or "") or ""
        if "# Compatibility Report" in body:
            return True
        for comment in issue.get("comments_data") or []:
            comment_body = (comment.get("body") or "") or ""
            if "# Compatibility Report" in comment_body:
                return True
        return False

    def filter(self):

        data = self.data
        issues = data["issues"]
        metadata = data.get("metadata") or {}
        filtered_issues = []

        for issue in issues:
            # rule 1
            state_reason = issue.get("state_reason")
            if state_reason in ("not_planned", "duplicate"):
                continue
            # rule 2
            comments_count = issue.get("comments", 0)
            comments_data = issue.get("comments_data") or []
            if comments_count <= 0 and len(comments_data) == 0:
                continue
            # rule 3
            if not self._has_formal_compatibility_report(issue):
                continue
            filtered_issues.append(issue)

        # renew meta info
        new_metadata = {**metadata, "total_issues_loaded": len(filtered_issues)}
        return {"metadata": new_metadata, "issues": filtered_issues}

    def handler(self):

        filtered_data = self.filter()
        chunk_divider(data=filtered_data, issues_per_file=50)





if __name__ == "__main__":
    data_filter = DataFilter()
    data_filter.handler()
