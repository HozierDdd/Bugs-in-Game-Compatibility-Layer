"""
Configuration for the CR characteristics LLM annotation pipeline.

Keep all business variables, paths, prompts, thresholds, and LLM settings here
so the workflow can be adjusted without editing implementation modules.
"""

from pathlib import Path
from typing import Literal

from src.config import (
    GITHUB_CHUNK_GLOB,
    GITHUB_CHUNKS_DIR,
    PROCESSED_DIR,
    PROTONDB_REPORTS_PATH,
    PROTONDB_TS_END,
    PROTONDB_TS_START,
    ROOT_DIR,
    TIME_WINDOW_END,
    TIME_WINDOW_START,
)


# -- Pipeline scope ---------------------------------------------------------

PIPELINE_NAME = "cr_characteristics"
PIPELINE_OUTPUT_DIR = PROCESSED_DIR / PIPELINE_NAME

PLATFORM_PROTONDB = "protondb"
PLATFORM_ISSUE_TRACKER = "issue_tracker"
PLATFORMS = (PLATFORM_PROTONDB, PLATFORM_ISSUE_TRACKER)

SCOPE_BY_PLATFORM = {
    PLATFORM_PROTONDB: "protondb_full",
    PLATFORM_ISSUE_TRACKER: "issue_tracker_full",
}

RANDOM_SEED = 20260427
CALIBRATION_SAMPLE_SIZE_PER_PLATFORM = 100
CALIBRATION_GROUP_SIZE = 5
REQUIRE_FULL_CALIBRATION_SAMPLE_SIZE = True
REQUIRE_ALL_CALIBRATION_GROUPS_FOR_GATE = True

FIELD_AGREEMENT_THRESHOLD = 0.85
ROUND_DIGITS = 4


# -- Input paths ------------------------------------------------------------

PROTONDB_INPUT_PATH = PROTONDB_REPORTS_PATH
ISSUE_TRACKER_CHUNKS_DIR = GITHUB_CHUNKS_DIR
ISSUE_TRACKER_CHUNK_GLOB = GITHUB_CHUNK_GLOB

TIME_WINDOW = {
    "start": TIME_WINDOW_START.isoformat(),
    "end": TIME_WINDOW_END.isoformat(),
}
PROTONDB_TIMESTAMP_START = PROTONDB_TS_START
PROTONDB_TIMESTAMP_END = PROTONDB_TS_END


# -- Output paths -----------------------------------------------------------

CALIBRATION_SAMPLE_PATH = PIPELINE_OUTPUT_DIR / "calibration_sample.json"
MANUAL_LABELS_TEMPLATE_PATH = PIPELINE_OUTPUT_DIR / "manual_labels_template.json"
LATEST_PREPARE_MANUAL_OUTPUT_PATH = PIPELINE_OUTPUT_DIR / "latest_prepare_manual_outputs.json"
LLM_CALIBRATION_LABELS_PATH = PIPELINE_OUTPUT_DIR / "llm_calibration_labels.jsonl"
CALIBRATION_REPORT_PATH = PIPELINE_OUTPUT_DIR / "calibration_report.json"
LLM_REMAINING_LABELS_PATH = PIPELINE_OUTPUT_DIR / "llm_remaining_labels.jsonl"
FINAL_LABELS_PATH = PIPELINE_OUTPUT_DIR / "final_labels.jsonl"
SUMMARY_OUTPUT_PATH = PIPELINE_OUTPUT_DIR / "summary.json"
FAILED_RECORDS_PATH = PIPELINE_OUTPUT_DIR / "failed_records.jsonl"

PREPARE_MANUAL_RUN_ID: str | None = None
PREPARE_MANUAL_RUN_ID_FORMAT = "%Y%m%d_%H%M%S"
CALIBRATION_SAMPLE_FILENAME_TEMPLATE = "calibration_sample_{run_id}.json"
MANUAL_LABELS_TEMPLATE_FILENAME_TEMPLATE = "manual_labels_template_{run_id}.json"
MANUAL_LABEL_GROUPS_DIR_TEMPLATE = "manual_label_groups_{run_id}"
MANUAL_LABEL_GROUP_FILENAME_TEMPLATE = "{platform}_group_{group_index:02d}.json"
CALIBRATION_GROUP_ID_TEMPLATE = "{platform}_group_{group_index:02d}"


# -- LLM settings -----------------------------------------------------------

ENV_FILE_PATH = ROOT_DIR / ".env"
ENV_FILE_ENCODING = "utf-8"
ENV_FILE_OVERRIDE_EXISTING = False

LLM_API_KEY_ENV = "OPENAI_API_KEY"
LLM_API_BASE_URL_ENV = "LLM_API_BASE_URL"
LLM_MODEL_ENV = "LLM_MODEL"

LLM_DEFAULT_API_BASE_URL = "https://api.openai.com/v1"
LLM_CHAT_COMPLETIONS_PATH = "/chat/completions"
LLM_DEFAULT_MODEL = "gpt-4.1-mini"
LLM_TEMPERATURE = 0.0
LLM_MAX_TOKENS = 1400
LLM_TIMEOUT_SECONDS = 60
LLM_RETRY_COUNT = 3
LLM_RETRY_BACKOFF_SECONDS = 2.0
LLM_RESPONSE_FORMAT = {"type": "json_object"}

ANNOTATION_BATCH_SIZE = 20
ANNOTATION_PROGRESS_INTERVAL = 25
EVIDENCE_MAX_CHARS = 280

ANNOTATION_SOURCE_LLM = "llm"
ANNOTATION_SOURCE_HUMAN_CALIBRATION = "human_calibration"


# -- Text cleaning / rendering ---------------------------------------------

HTML_COMMENT_PATTERN = r"<!--.*?-->"
EMPTY_FIELD_PLACEHOLDER = ""
RECORD_TEXT_MAX_CHARS = 24000

PROTONDB_RENDERED_SECTIONS = (
    "metadata",
    "systemInfo",
    "responses",
)

ISSUE_TRACKER_POST_KINDS = {
    "issue_body": "issue_body",
    "comment": "comment",
}


# -- CR characteristics -----------------------------------------------------

CHARACTERISTIC_KEYS = (
    "observed_behavior",
    "expected_behavior",
    "proton_version",
    "steps_to_reproduce",
    "test_cases_or_examples",
    "component",
    "program_output",
    "user_environment",
    "screenshot",
    "product",
)

CHARACTERISTICS = {
    "observed_behavior": {
        "label": "Observed behavior",
        "definition": (
            "The report describes what actually happened, such as a crash, "
            "black screen, broken audio, degraded performance, or another "
            "compatibility symptom."
        ),
    },
    "expected_behavior": {
        "label": "Expected behavior",
        "definition": (
            "The report states what the user expected instead, including a "
            "comparison to Windows/native behavior, a previous working Proton "
            "version, or the intended game behavior."
        ),
    },
    "proton_version": {
        "label": "Proton version",
        "definition": (
            "The report names a Proton version, Proton Experimental, Proton "
            "GE, Proton Hotfix, or another Proton runtime variant."
        ),
    },
    "steps_to_reproduce": {
        "label": "Steps to reproduce",
        "definition": (
            "The report gives concrete actions that can reproduce the issue, "
            "including numbered steps, bullet steps, or a concise reproduction "
            "sentence."
        ),
    },
    "test_cases_or_examples": {
        "label": "Test cases or example",
        "definition": (
            "The report includes specific examples, scenarios, saves, levels, "
            "settings, commands, launch options, comparisons, or attempts that "
            "serve as test cases."
        ),
    },
    "component": {
        "label": "Component",
        "definition": (
            "The report names a relevant component or subsystem, such as EAC, "
            "launcher, Vulkan, DXVK, VKD3D, Media Foundation, controller input, "
            "audio, networking, overlay, shaders, or a game-specific module."
        ),
    },
    "program_output": {
        "label": "Program output",
        "definition": (
            "The report includes logs, error messages, stack traces, crash "
            "dumps, terminal output, dialog text, exception codes, or links to "
            "log/error files."
        ),
    },
    "user_environment": {
        "label": "User environment",
        "definition": (
            "The report includes OS, distro, kernel, CPU, GPU, GPU driver, RAM, "
            "Steam Deck, desktop environment, or support software details."
        ),
    },
    "screenshot": {
        "label": "Screenshot",
        "definition": (
            "The report includes an embedded image, screenshot, image URL, or "
            "a clear reference to an attached screenshot."
        ),
    },
    "product": {
        "label": "Product (Game name)",
        "definition": (
            "The report identifies the affected game or product name and/or "
            "Steam AppID."
        ),
    },
}


# -- Prompt templates -------------------------------------------------------

SYSTEM_PROMPT = """
You are a careful research annotator for Linux game compatibility reports.
Your task is to decide whether a compatibility report contains each requested
information type. Mark a characteristic as present only when the report itself
contains direct evidence for it. Do not infer missing facts from outside
knowledge. Treat URLs, attachment names, logs, code blocks, and structured form
fields as valid evidence when they contain the requested information.

Return only valid JSON. The JSON must have this shape:
{
  "labels": {
    "<characteristic_key>": {"present": true or false, "evidence": "short quote or paraphrase"}
  },
  "notes": "optional short note"
}
Every characteristic key must be present exactly once. Evidence must be empty
when present is false.
""".strip()

PROTONDB_USER_PROMPT_TEMPLATE = """
Platform: ProtonDB

ProtonDB reports are structured form submissions. Field names such as
systemInfo.gpu, responses.protonVersion, responses.notes.*, and
responses.concludingNotes are part of the compatibility report and may count as
evidence. Use both field names and field values when deciding whether a
characteristic is covered.

Characteristics to annotate:
{characteristics_json}

Record metadata and rendered compatibility report:
{record_json}

Rendered report text:
{record_text}
""".strip()

ISSUE_TRACKER_USER_PROMPT_TEMPLATE = """
Platform: ValveSoftware/Proton issue tracker

Issue tracker compatibility reports are markdown posts. Template field names,
markdown sections, links, attachments, code blocks, and quoted error messages
may count as evidence. Ignore boilerplate instructions that are only HTML
comments; the provided text has already removed those comments.

Characteristics to annotate:
{characteristics_json}

Record metadata and rendered compatibility report:
{record_json}

Rendered report text:
{record_text}
""".strip()

PROMPT_TEMPLATE_BY_PLATFORM = {
    PLATFORM_PROTONDB: PROTONDB_USER_PROMPT_TEMPLATE,
    PLATFORM_ISSUE_TRACKER: ISSUE_TRACKER_USER_PROMPT_TEMPLATE,
}


# -- Manual template fields -------------------------------------------------

HUMAN_LABELS_FIELD = "human_labels"
HUMAN_NOTES_FIELD = "human_notes"
LLM_LABELS_FIELD = "llm_labels"
LABEL_PRESENT_FIELD = "present"
LABEL_EVIDENCE_FIELD = "evidence"


# -- Main entry -------------------------------------------------------------
#
# Run from repo root: python3 -m src.cr_characteristics_pipeline
# Switch stage by editing PIPELINE_RUN_STAGE and the flags below.

PipelineRunStage = Literal["prepare_manual", "calibrate", "label_remaining", "summarize"]

PIPELINE_RUN_STAGE: PipelineRunStage = "calibrate"

CALIBRATE_USE_MOCK_LLM = False
CALIBRATE_FORCE = False

LABEL_REMAINING_USE_MOCK_LLM = False
LABEL_REMAINING_FORCE = False
LABEL_REMAINING_LIMIT: int | None = None

# Set to a specific completed manual-label file to calibrate/summarize an older
# sample. Keep as None to use latest_prepare_manual_outputs.json.
MANUAL_LABELS_PATH: Path | str | None = None
