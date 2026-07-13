import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

SYSTEM_PROMPT = """
You are an expert auditor for ProtonDB compatibility report data. Your task is to determine whether a given ProtonDB report contains specific types of compatibility-report information.

The user will provide one ProtonDB report as a JSON string. The JSON may contain structured fields such as game title, app ID, rating, Proton version, system information, hardware information, OS or distro, GPU, driver, CPU, RAM, notes, description, summary, user comments, timestamp, or other metadata.

You must inspect all available fields in the JSON string, including nested objects and arrays.

For each category, return true if the ProtonDB report explicitly contains that type of information, and false if it does not.

Do not infer missing information.
Do not mark a category as true just because it could be guessed from another field.
If a field exists but is empty, null, unknown, "N/A", or only contains placeholder text, treat it as not present.
If the information is present anywhere in the JSON, even under a different field name, count it as present.

Categories to audit:

1. observed_behavior
True if the report contains a user-written textual description in the notes, concludingNotes, or other free-text fields of what actually happened when running the game, such as crash, freeze, failure to launch, stuttering, poor FPS, graphical glitches, missing audio, input problems, multiplayer issues, video playback issues, broken features, or statements such as "works perfectly", "runs well", "no issues", or "playable".
False if the report only gives a rating without describing behavior. Structured checkbox fields such as verdict, installs, opens, startsPlay, verdictOob, triedOob (with values like "yes" or "no") are form metadata and do NOT count as observed behavior — they are equivalent to a rating. There must be actual user-written text describing what happened.

2. expected_behavior
True if the report explicitly states what the user expected or wanted to happen, such as the game should launch, should run smoothly, should display correctly, should support multiplayer, should play videos, or should work like on Windows.
False if only the actual behavior is described.

3. proton_version
True if the report includes a Proton version, Proton branch, or compatibility tool, such as Proton Experimental, Proton 9.0, Proton 10.0, GE-Proton, Proton-GE, Steam Play, or a specific compatibility-tool version.

4. steps_to_reproduce
True if the report provides explicit, user-written actions or instructions that would help someone reproduce the problem or behavior, such as specific in-game steps or a sequence of actions that leads to the issue described in the notes or concludingNotes.
False if the user only describes a workaround, fix, or tip (e.g., "delete compatdata to fix it", "just wait", "disable v-sync to fix stuttering", "remap the controls"). Workarounds explain how to solve or avoid a problem, not how to reproduce it — they do NOT count. Also false if the only relevant information is a launchOptions field or structured checkbox metadata. The launchOptions field alone does NOT count — it is a configuration detail, not a reproduction procedure. Similarly, structured fields like installs/opens/startsPlay are metadata, not steps.

5. test_cases_or_example
True if the user describes a concrete tested scenario in their notes or concludingNotes. This includes but is not limited to: a specific game mode, level, map, mission, graphics setting, multiplayer session, controller type, save file, benchmark, or a specific feature they tested. It also includes testing a specific external configuration, hardware interaction, or tool to verify whether it works — for example, testing whether disabling PulseAudio fixes audio, testing controller input recognition, testing a secondary launcher, testing multiplayer connectivity, testing community button layouts on Steam Deck, or testing a specific Proton version to compare performance.
False if the report only contains structured checkbox responses (audioFaults, graphicalFaults, etc.) without a user-written description of a specific scenario. A general rating or general statement like "runs fine" or "runs pretty good" alone is not enough — there must be a specific scenario or configuration that was tested. A bare URL or video link without accompanying text describing a tested scenario does NOT count. Mentioning a specific map name, level, or mode in passing within notes DOES count if it clearly identifies a concrete scenario tested.

6. component
True if the user explicitly names or describes a specific software or game component involved in the behavior in their notes, concludingNotes, or free-text fields — such as "Steam Overlay", "anti-cheat", "Origin launcher", "DXVK", "VKD3D", "Wine", "PulseAudio", "video playback", or a specific DLL/library.
False if the only evidence comes from structured checkbox fields like audioFaults, graphicalFaults, inputFaults, stabilityFaults, etc. These are ProtonDB form metadata and do NOT count as identifying a component. Also false if the report only names hardware or the game title.

7. program_output
True if the report includes or links to logs, error messages, crash reports, stack traces, terminal output, exception messages, Proton logs, debug output, or diagnostic reports.
False if it only contains user comments without output or links to output.

8. user_environment
True if the report includes user environment information, such as OS, Linux distribution, kernel version, GPU, CPU, RAM, driver version, desktop environment, compositor, Steam Deck, hardware model, or other system/support software information.

9. media
True if the report includes or links to a screenshot, image, video capture, screen recording, or visual evidence.
False if it only includes text, logs, ratings, or system information.

10. product_game_title
True if the report includes the game title, Steam AppID, ProtonDB game ID, slug, store link, or another clear identifier of the affected product/game.

Important rules:
- Structured checkbox fields such as verdict, installs, opens, startsPlay, verdictOob, and triedOob are form metadata equivalent to a rating — they do NOT count as observed_behavior. Only user-written text in notes, concludingNotes, or other free-text fields counts.
- A ProtonDB report saying "works out of the box", "runs perfectly", "no issues", or similar IN USER-WRITTEN TEXT counts as observed_behavior because it describes the actual result in the user's own words.
- If a report has no user-written text at all (empty or missing notes and concludingNotes), observed_behavior should be false regardless of what the structured fields say.
- Hardware fields such as GPU, CPU, driver, distro, kernel, or Steam Deck count as user_environment.
- Game title, app ID, or slug counts as product_game_title.
- The launchOptions field alone does NOT count as steps_to_reproduce. Only user-written procedural instructions in notes or concludingNotes count.
- Workarounds, fixes, and tips (e.g., "delete compatdata", "just wait", "disable v-sync") are NOT steps_to_reproduce. Steps to reproduce must describe how to trigger or recreate the problem, not how to solve it.
- Structured checkbox fields (audioFaults, graphicalFaults, inputFaults, stabilityFaults, windowingFaults, performanceFaults, saveGameFaults, etc.) are ProtonDB form metadata and do NOT count as identifying a component. Only explicit mentions of a component name in user-written text count.
- VR streaming tools (e.g., ALVR), system-level features (e.g., FSR), and hardware peripherals (e.g., Steam Deck, Quest 2) are NOT software or game components — do not mark component as true for these.
- The variant field (e.g., "official", "ge", "older") is a ProtonDB form category, NOT a Proton version. Do not treat it as proton_version.
- test_cases_or_example covers any concrete, specific scenario the user tested — including testing specific external configurations, hardware interactions, or tools (not just in-game scenarios). However, a general statement like "runs fine" or "runs pretty good" alone is NOT enough, and a bare URL or video link without text describing a tested scenario is NOT enough.
- Do not treat automatically generated metadata as expected_behavior unless it explicitly states an expected outcome.
- Prioritize user-written text (notes, concludingNotes) over structured checkbox metadata for all categories.

Return only valid JSON.
Do not include Markdown.
Do not include explanations outside the JSON.

Use exactly this JSON schema:

{
  "observed_behavior": true or false,
  "expected_behavior": true or false,
  "proton_version": true or false,
  "steps_to_reproduce": true or false,
  "test_cases_or_example": true or false,
  "component": true or false,
  "program_output": true or false,
  "user_environment": true or false,
  "media": true or false,
  "product_game_title": true or false
}
"""


def load_environment() -> tuple[str, str, float]:
    project_root = Path(__file__).resolve().parents[2]
    env_path = project_root / ".env"

    load_dotenv(env_path)

    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0"))

    if not api_key:
        raise ValueError(f"OPENAI_API_KEY is not found. Checked: {env_path}")

    if not model:
        raise ValueError(f"OPENAI_MODEL is not found. Checked: {env_path}")

    return api_key, model, temperature


def create_client(api_key: str) -> OpenAI:
    return OpenAI(api_key=api_key)


def label_single(client: OpenAI, model: str, temperature: float, report_json: str) -> dict:
    """Label a single ProtonDB report (passed as a JSON string) and return the parsed dict."""
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=report_json,
        temperature=temperature,
    )
    return json.loads(response.output_text)


def main() -> None:
    api_key, model, temperature = load_environment()
    client = create_client(api_key)

    sample = {
        "app": {"steam": {"appId": "506510"}, "title": "Shadows of Adam"},
        "responses": {
            "answerToWhatGame": "506510",
            "audioFaults": "no",
            "concludingNotes": "The native version does not work for me so I have to try the proton ones. Only Proton 4.11 makes it work and it works really well. All other versions shows a white screen.",
            "graphicalFaults": "no",
            "inputFaults": "no",
            "installs": "yes",
            "launchOptions": "prime-run %command%",
            "notes": {"verdict": "As long as using Proton 4.11 the game will work without any issue."},
            "protonVersion": "4.11-12",
            "verdict": "yes",
        },
        "timestamp": 1650941514,
        "systemInfo": {
            "cpu": "11th Gen Intel Core i9-11900H @ 2.50GHz",
            "gpu": "NVIDIA GeForce RTX 3080 Laptop GPU",
            "gpuDriver": "NVIDIA 510.60.02",
            "kernel": "5.17.4-arch1-1",
            "os": "ArcoLinux",
            "ram": "32 GB",
        },
    }

    result = label_single(client, model, temperature, json.dumps(sample, ensure_ascii=False))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
