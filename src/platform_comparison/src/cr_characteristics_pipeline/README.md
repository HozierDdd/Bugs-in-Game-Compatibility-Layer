# CR Characteristics LLM Labeling Pipeline

This folder contains a standalone LLM labeling flow that decides whether the compatibility reports on ProtonDB and the Proton issue tracker cover each of 10 CR characteristics:

- Observed behavior
- Expected behavior
- Proton version
- Steps to reproduce
- Test cases or example
- Component
- Program output
- User environment
- Screenshot
- Product (Game name)

This flow is intentionally kept out of the existing `run_pipeline.py` step0-step9, so LLM labeling is not coupled to the current deterministic statistics pipeline. All paths, thresholds, prompts, LLM parameters, and field definitions live in `config.py`.

## How to run

Set the current stage and options in the **"Main entry"** section at the end of **`config.py`**, then run from the **repository root** (no subcommands, no program arguments):

```bash
python3 -m src.cr_characteristics_pipeline
```

`__main__.py` calls `main.main()`; you can also run `main.py` directly (as long as the working directory and `PYTHONPATH` match the above).

**`PIPELINE_RUN_STAGE` values** (one per step):

| Value | Meaning |
| --- | --- |
| `prepare_manual` | Randomly sample and generate the manual-labeling templates |
| `calibrate` | Run the LLM over the calibration set and write the calibration report |
| `label_remaining` | Label every CR outside the calibration set (requires the gate to pass) |
| `summarize` | Merge manual + LLM labels and emit the final labels and summary |

**Common switches** (all in `config.py`):

- `PREPARE_MANUAL_RUN_ID`: optional sampling run ID; defaults to an automatic UTC timestamp.
- `CALIBRATE_USE_MOCK_LLM` / `CALIBRATE_FORCE`: use a mock LLM during calibration; overwrite an existing calibration JSONL.
- `LABEL_REMAINING_USE_MOCK_LLM` / `LABEL_REMAINING_FORCE` / `LABEL_REMAINING_LIMIT`: mock, overwrite, and record-count cap for the remaining labeling.
- `MANUAL_LABELS_PATH`: point at a specific group file or group directory; the default `None` means auto-scan the group files of the latest run.

In an IDE: **run it as a module** (`src.cr_characteristics_pipeline`), do **not** pass program arguments; to change stage, just edit constants such as `config.PIPELINE_RUN_STAGE`.

## Workflow

### 1. Randomly draw the manual calibration sample

Set `PIPELINE_RUN_STAGE` to `"prepare_manual"`.

By default it draws 100 CRs without replacement from each platform:

- ProtonDB: 100
- Proton issue tracker: 100

The output files carry a fresh `run_id` every time and never overwrite older templates:

- `data/processed/cr_characteristics/calibration_sample_<run_id>.json`
- `data/processed/cr_characteristics/manual_labels_template_<run_id>.json`
- `data/processed/cr_characteristics/manual_label_groups_<run_id>/protondb_group_01.json` ... `protondb_group_20.json`
- `data/processed/cr_characteristics/manual_label_groups_<run_id>/issue_tracker_group_01.json` ... `issue_tracker_group_20.json`
- `data/processed/cr_characteristics/latest_prepare_manual_outputs.json`

The manual-labeling entry point is the group files under `manual_label_groups_<run_id>/`: 20 groups per platform, 5 records per group. Go through each group file and change `human_labels` from `null` to `true` or `false`. `manual_labels_template_<run_id>.json` is only a merged view kept for the old flow; editing it directly is discouraged.

The latest group paths are also written to `latest_prepare_manual_outputs.json`; when `config.MANUAL_LABELS_PATH = None`, later stages auto-scan those group files.

Sampling is controlled by `config.RANDOM_SEED`; the same seed yields the same sample.

### 2. Fill in calibration labels group by group

Each platform has 20 groups of 5 CRs each. You can label a few groups first and then run `calibrate` to check the current prompt's agreement, without filling in all 200 records at once.

Each record contains:

- `record_id`
- `platform`
- `app_id`
- `title`
- `created_at`
- `text`
- `human_labels`

You only need to edit `human_labels` and the optional `human_notes`. Example of the final structure:

```json
"human_labels": {
  "observed_behavior": true,
  "expected_behavior": false,
  "proton_version": true,
  "steps_to_reproduce": true,
  "test_cases_or_examples": false,
  "component": false,
  "program_output": true,
  "user_environment": true,
  "screenshot": false,
  "product": true
}
```

### 3. Run prompt calibration

Put your API key in the `.env` at the repo root. Set `PIPELINE_RUN_STAGE` to `"calibrate"`, set `CALIBRATE_FORCE` / `CALIBRATE_USE_MOCK_LLM` as needed, then run the main program.

`calibrate` scans all group files under the latest run and processes only the groups that are fully filled in:

- A group counts as complete only when all 10 `human_labels` of its 5 records are `true/false`.
- Incomplete groups are skipped and do not block the dynamic evaluation.
- Records already written to `llm_calibration_labels.jsonl` are skipped automatically, so you can re-run `calibrate` after finishing each few groups.

The LLM labels the currently completed groups and then compares against the manual labels.

Output files:

- `data/processed/cr_characteristics/llm_calibration_labels.jsonl`
- `data/processed/cr_characteristics/calibration_report.json`
- `data/processed/cr_characteristics/failed_records.jsonl` (appended only on failures)

`calibration_report.json` reports, per platform:

- field-level agreement
- record-level exact match
- per-characteristic precision / recall / F1 / accuracy
- per-group metrics
- current progress: completed groups / total groups

The default gate is that all groups are complete and both platforms' field-level agreement reaches `config.FIELD_AGREEMENT_THRESHOLD`, currently `0.85`. If either platform falls short or groups are incomplete, the later `label_remaining` stage is blocked. In that case, finish the remaining groups or adjust the relevant prompt in `config.py`, then re-run calibration.

Smoke test without hitting the real API: `CALIBRATE_USE_MOCK_LLM = True` and `CALIBRATE_FORCE = True`.

### 4. Label all remaining CRs

Set `PIPELINE_RUN_STAGE` to `"label_remaining"`, then run the main program.

This step first checks the gate in `calibration_report.json`. Only if the gate passes does it label every CR outside the calibration set.

Output file:

- `data/processed/cr_characteristics/llm_remaining_labels.jsonl`

This step supports resuming: `record_id`s already written to the JSONL are skipped automatically.

For debugging, set `LABEL_REMAINING_LIMIT` (e.g. `20`) to cap the number of new labels.

### 5. Summarize the final results

Set `PIPELINE_RUN_STAGE` to `"summarize"` and run the main program.

Output files:

- `data/processed/cr_characteristics/final_labels.jsonl`
- `data/processed/cr_characteristics/summary.json`

In the final results, the calibration set uses the manual labels as authoritative; the remaining CRs use the LLM labels.

## Editing the prompts

Both platforms' prompts live in `config.py`:

- `PROTONDB_USER_PROMPT_TEMPLATE`
- `ISSUE_TRACKER_USER_PROMPT_TEMPLATE`
- `SYSTEM_PROMPT`

The definitions of the 10 fields are in `CHARACTERISTICS`. If calibration shows a field with poor precision or recall, first refine that field's definition or the relevant platform prompt.

## LLM API configuration

By default it uses an OpenAI-compatible `/chat/completions` endpoint and adds no third-party SDK dependency.

Configurable environment variables go in the `.env` at the repo root, and can also be overridden by shell environment variables:

- `OPENAI_API_KEY`: API key; the variable name is controlled by `config.LLM_API_KEY_ENV`
- `LLM_API_BASE_URL`: API base URL, defaults to `https://api.openai.com/v1`
- `LLM_MODEL`: model, default controlled by `config.LLM_DEFAULT_MODEL`

`.env` example:

```dotenv
OPENAI_API_KEY=replace_with_your_openai_api_key
LLM_API_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4.1-mini
```

Other parameters in `config.py`:

- `LLM_TEMPERATURE`
- `LLM_MAX_TOKENS`
- `LLM_TIMEOUT_SECONDS`
- `LLM_RETRY_COUNT`
- `LLM_RETRY_BACKOFF_SECONDS`

## Code structure

- `config.py`: all business variables, paths, prompts, thresholds, LLM parameters, and the main-entry stage/switches
- `records.py`: extract post-level CRs from ProtonDB and the issue tracker and render them as LLM input text
- `prompts.py`: build messages from the prompt templates in config
- `llm_client.py`: OpenAI-compatible client and mock client
- `annotator.py`: LLM calls, JSON-schema validation, resumable writes
- `evaluation.py`: calibration metrics, gate, and final aggregation
- `storage.py`: JSONL utilities
- `main.py`: `main()` and the implementation of each step
- `__main__.py`: package module entry; invokes `main.main()` on `python3 -m src.cr_characteristics_pipeline`

## Data conventions

ProtonDB:

- reads `data/protondb/reports_piiremoved.json`
- filters with the global time window
- each ProtonDB report is one CR
- renders `systemInfo.*`, `responses.*`, and `responses.notes.*`

Proton issue tracker:

- reuses `src.loaders.github_loader.iter_github_issues`
- reuses `src.parsers.compatibility_report_classifier.classify_post`
- the issue body and each comment are judged as independent posts
- only posts containing `# Compatibility Report` enter this pipeline
- HTML comment boilerplate is stripped before being sent to the LLM

## Output format

Each LLM label record contains:

```json
{
  "record_id": "issue_tracker:9287:body",
  "platform": "issue_tracker",
  "scope": "issue_tracker_full",
  "app_id": "2070270",
  "title": "Cloudheim (2070270)",
  "source": "llm",
  "labels": {
    "observed_behavior": true,
    "expected_behavior": false
  },
  "evidence": {
    "observed_behavior": "Game crashes after a couple minutes",
    "expected_behavior": ""
  }
}
```

The actual `labels` and `evidence` include all 10 characteristics.
