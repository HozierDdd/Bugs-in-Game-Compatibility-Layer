# Data Collection & Symptom Taxonomy (Proton GitHub Issue Tracker)

Code for collecting compatibility reports (CRs) from the
`ValveSoftware/proton` GitHub issue tracker (ProtonGT) and for building the
RQ2 symptom taxonomy.

This module covers two parts of the paper:

- **Data collection (Section III.B):** retrieve ProtonGT threads via the GitHub
  REST API, filter them to the 2021–2025 window, and identify CRs by their
  `# Compatibility Report` header.
- **RQ2 taxonomy pipeline (Section IV.B, Fig. 4):** sample CRs, attach each
  CR's follow-up discussion, label discussion relevance, and support the manual
  open card sorting used to build the 9-category / 25-subcategory taxonomy.
  The taxonomy itself is built by two annotators through open card sorting; the
  scripts here prepare the data and compute inter-annotator agreement.

> The symptom taxonomy is produced by **manual open card sorting**, not by an
> LLM or keyword matching. The only LLM-assisted step in the paper (RQ1 content
> coding, Claude Opus 4.8) lives in a different module (`cr_content_labeling/`).

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. (Optional) Set up a GitHub token for higher rate limits:
```bash
cp .env.example .env      # then edit GITHUB_TOKEN
# or
export GITHUB_TOKEN=your_github_token_here
```

## Directory Layout

```
data_collection_and_taxonomy/
├── utls/
│   ├── data_collector.py     # collect ProtonGT issues + comments via GitHub API
│   ├── data_divider.py        # split a large collected JSON into per-chunk files
│   └── utls.py                # shared I/O helpers (chunk_loader / chunk_divider / root finder)
├── data_select_pipeline/
│   ├── data_filter.py                     # apply the three CR filtering rules
│   ├── issue_selector.py                  # sample issues by year (2021–2024) and state
│   ├── compatibility_report_selector.py   # extract all CRs, then draw the 330-CR sample
│   └── report_discussion_pair_collector.py# attach each CR's following discussion (<= 50)
└── data_analysis_pipeline/
    ├── comp_report_analyzer.py            # RQ2 symptom-label agreement (Cohen's kappa)
    └── report_discussion_analyzer.py      # discussion-relevance agreement (Cohen's kappa)
```

## Pipeline

The scripts run in order; each stage reads the previous stage's output under a
local `data/` directory (not shipped in the artifact; see *Data* below).

### 1. Collect (`utls/data_collector.py`)

Collect all issues (open and closed) with comments:
```bash
python utls/data_collector.py
```

Common options:
- `--state {open,closed,all}` — filter by issue state (default: all)
- `--max-issues N` — limit the number of issues collected
- `--output-dir DIR` — output directory (default: `data/issue_origin`)
- `--token TOKEN` — GitHub personal access token
- `--no-comments` — skip collecting comments (faster)
- `--output FILE` — output filename (default: auto-generated with timestamp)

Output is a JSON file with `metadata` (repository, date, totals) and `issues`
(each issue plus its `comments_data`). `utls/data_divider.py` splits a large
collected file into smaller per-chunk files for the next stage.

### 2. Filter (`data_select_pipeline/data_filter.py`)

Keeps a thread only if it passes three rules:
1. it was not closed as `not_planned` or `duplicate`;
2. it has at least one comment;
3. it contains a formal `# Compatibility Report` (in the body or a comment).

### 3. Sample issues by time and state (`data_select_pipeline/issue_selector.py`)

Groups the filtered issues by creation year and by open/closed state, feeding
the CR sampling frame for RQ2 (threads created within 2021–2025).

### 4. Extract CRs and draw the 330-CR sample (`data_select_pipeline/compatibility_report_selector.py`)

Extracts every CR that is followed by at least one non-report comment
(`all_report.json`, the sampling frame), then draws a fixed random sample of
**330 CRs** (`random_sampling_report.json`). Sampling uses `seed=12345` for
reproducibility.

### 5. Attach following discussion (`data_select_pipeline/report_discussion_pair_collector.py`)

For each sampled CR, collects the comments posted after it (excluding other
reports, capped at 50, ordered by time) into `report_discussion_pair.json`.
The `is_for_the_report` field is left `null` for annotators to fill in.

### 6. Manual annotation (external)

Two annotators then (a) label each discussion as related/unrelated to its CR
and (b) code symptoms via open card sorting, iterating until the taxonomy
stabilizes. The resulting labeled dataset is in the top-level
`labeled_dataset/` of the artifact.

### 7. Inter-annotator agreement (`data_analysis_pipeline/`)

- `report_discussion_analyzer.py` — Cohen's kappa for the discussion-relevance
  labels (`is_for_the_report`), matched by `(issue_number, discussion_url)`.
- `comp_report_analyzer.py` — Micro Cohen's kappa for the symptom `tags` over
  the reliability batches (parts 27–33), the RQ2 sub-category agreement
  (κ = 0.77 in the paper).

## Data

The raw and intermediate `data/` directory is **not** included in this module
(it is several GB). Rebuild it by running stage 1 above, then stages 2–5. The
manually labeled dataset used in the paper is provided separately under the
artifact's `labeled_dataset/`.

## GitHub API Rate Limits

- Without authentication: 60 requests/hour
- With authentication: 5,000 requests/hour

A personal access token is recommended for large collections.
