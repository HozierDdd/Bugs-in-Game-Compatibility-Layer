"""
Labeled report analyzer: load JSON data and compute labeling agreement (Cohen's Kappa).
"""
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from utls.utls import chunk_loader

import json
from sklearn.metrics import cohen_kappa_score


def _find_root_directory() -> Path:
    """Find project root directory (parent that contains 'data')."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "data").is_dir():
            return parent
    return Path(__file__).resolve().parent.parent


def _extract_label_pairs(
    data: List[Dict[str, Any]],
) -> Dict[Tuple[int, str], str]:
    """
    Extract (issue_number, discussion_html_url) -> is_for_the_report label from report list.

    Returns:
        (issue_number, discussion_html_url) -> "true" | "false" | "not_sure"
    """
    out: Dict[Tuple[int, str], str] = {}
    for report in data:
        issue_number = report.get("issue_number")
        if issue_number is None:
            print("ERROR: missing issue number")
            continue
        for disc in report.get("following_discussion") or []:
            url = disc.get("discussion_html_url")
            label = disc.get("is_for_the_report")
            if url is None or label is None:
                print(f"ERROR: missing issue #{issue_number} discussion url or label")
                continue
            label = str(label).strip().lower()
            if label not in ("true", "false", "not_sure"):
                print(f"ERROR: missing issue #{issue_number} label")
                continue
            out[(issue_number, url)] = label
    return out


class LabeledReportAnalyzer:
    """Labeled report analyzer: load JSON, compute Cohen's Kappa, etc."""


    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = root_dir or _find_root_directory()

    def _load_json(self, file_path: Path) -> List[Dict[str, Any]]:
        """Load JSON as list of reports."""
        path = file_path if file_path.is_absolute() else self.root_dir / file_path
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def cohens_kappa_calculator(
        self,
        file_path: Optional[Path] = None,
        file_path_rater2: Optional[Path] = None,
    ) -> Optional[float]:
        """
        Compute Cohen's Kappa from "is_for_the_report": "true" / "false" / "not_sure" in JSON.

        - If two file paths are given: treat as two raters, match by (issue_number, discussion_html_url), then compute Kappa.
        - If only one file path is given: use the same file as both raters (self-consistency), Kappa is 1.0.

        Args:
            file_path: First annotation JSON path; default is project's Label Studio Lite Report Feb 25 2026.json.
            file_path_rater2: Second annotation JSON path; if omitted, only file_path is used (kappa=1.0).

        Returns:
            Cohen's Kappa value; None if no common samples.
        """
        path1 = file_path
        # data1 = self._load_json(path1)
        data1 = []
        chunk_1 = chunk_loader(path1)
        for chunk in chunk_1:
            for item in chunk:
                data1.append(item)
        labels1 = _extract_label_pairs(data1)

        if file_path_rater2 is not None:
            data2 = []
            chunk_2 = chunk_loader(file_path_rater2)
            for chunk in chunk_2:
                for item in chunk:
                    data2.append(item)
            labels2 = _extract_label_pairs(data2)
            common_keys = sorted(set(labels1.keys()) & set(labels2.keys()))
            if not common_keys:
                print("ERROR: No common samples between the two raters; cannot compute Cohen's Kappa.")
                return None
            total_rater1 = len(labels1)
            total_rater2 = len(labels2)
            n_common = len(common_keys)
            if n_common != total_rater1 or n_common != total_rater2:
                print(
                    f"ERROR: Intersection size ({n_common}) does not equal sample total: "
                    f"Rater1 has {total_rater1} samples, Rater2 has {total_rater2} samples. "
                    "Both raters must label the same set of samples."
                )
            y1 = [labels1[k] for k in common_keys]
            y2 = [labels2[k] for k in common_keys]
            kappa = cohen_kappa_score(y1, y2)
        else:
            print("ERROR: needs second rater or rater2 to compute Cohen's Kappa.")

        print(f"Cohen's Kappa = {kappa}")
        return kappa


if __name__ == "__main__":
    analyzer = LabeledReportAnalyzer()
    file_path = Path("data/compatibility_report_selection/cr_discussion_data(labeled)")
    file_path_2 = Path("data/compatibility_report_selection/cr_discussion_data(labeled)/annotator_A")
    analyzer.cohens_kappa_calculator(file_path,
                                     file_path_2)
