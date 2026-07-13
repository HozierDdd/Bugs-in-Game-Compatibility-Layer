import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

SYSTEM_PROMPT = """
You are an expert auditor for Proton compatibility reports.

Your task is to determine whether a given compatibility report contains specific types of information.
For each category, return true if the report explicitly contains that information, and false if it does not.

You must only judge based on the content provided in the report body, title, labels, metadata, and URL if available.
Do not infer missing information unless it is clearly stated.
Do not mark a category as true just because it is implied by another category.

Definitions of categories:

1. observed_behavior
True if the report describes what actually happens, such as a crash, freeze, rendering issue, missing overlay, poor performance, wrong behavior, or any symptom experienced by the user.

2. expected_behavior
True if the report explicitly describes what the user expected to happen, such as "should launch", "expected to work", "should display correctly", or "I need it to invite friends".
False if only the problem is described without an explicit expected outcome.

3. proton_version
True if the report includes a Proton version, such as "Proton 10.0-2", "Experimental", "GE-Proton", or similar.

4. steps_to_reproduce
True if the report provides reproduction steps, launch instructions, conditions, or actions needed to trigger the issue.

5. test_cases_or_example
True if the report provides a concrete test case, example scenario, command, configuration, save file, specific mode, or concrete in-game action used to demonstrate the issue.
A general symptom alone is not enough.

6. component
True if the report identifies a technical component involved in the issue, such as Steam Overlay, graphics, audio, controller input, networking, multiplayer, video playback, launcher, anti-cheat, DXVK, VKD3D, Wine, or another subsystem.

7. program_output
True if the report includes or links to program output, such as a log file, error report, crash dump, stack trace, terminal output, or Proton log.

8. user_environment
True if the report includes information about the user's environment, such as operating system, kernel version, GPU, CPU, driver version, desktop environment, hardware, or support software.

9. media
True if the report includes or links to a screenshot, image, screen recording, or visual evidence.
False if it only includes logs or text links.

10. product_game_title
True if the report includes the product or game title, Steam AppID, or other clear identifier of the affected game/application.

Output requirements:

Return only valid JSON.
Do not include Markdown.
Do not include explanations outside the JSON.
Use exactly the following JSON schema:

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

Be conservative:
- If the evidence is vague or absent, return false.
- If a category is only mentioned in an instruction template or HTML comment but not filled in by the user, return false.
- Links to actual uploaded logs count as program_output.
- Links to Gists containing system information count as user_environment if the report clearly says they are system information reports.
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


def label_single(client: OpenAI, model: str, temperature: float, body: str) -> dict:
    """Label a single compatibility report body and return the parsed JSON dict."""
    response = client.responses.create(
        model=model,
        instructions=SYSTEM_PROMPT,
        input=body,
        temperature=temperature,
    )
    return json.loads(response.output_text)


def main() -> None:
    api_key, model, temperature = load_environment()
    client = create_client(api_key)

    user_prompt = (
        "# Compatibility Report\n"
        "- Name of the game with compatibility issues: Umihara Kawase BaZooKa!\n"
        "- Steam AppID of the game: 1271620\n\n"
        "## System Information\n"
        "- GPU: Radeon RX 7900 XT\n"
        "- Video driver version: 4.6 (Compatibility Profile) Mesa 25.2.6-arch1.1\n"
        "- Kernel version: 6.17.7-arch1-1\n"
        "- Link to full system information report as [Gist](https://gist.github.com/): "
        "https://gist.github.com/StoneGreninja/1e1d27760e684b9a8724d66e3b04198d\n"
        "- Proton version: 10.0-2 (beta)\n\n"
        "## I confirm:\n"
        "- [ X ] that I haven't found an existing compatibility report for this game.\n"
        "- [ X ] that I have checked whether there are updates for my system available.\n\n"
        "[steam-1271620.log](https://github.com/user-attachments/files/23429446/steam-1271620.log)\n\n"
        "## Symptoms\n\n"
        "I can't open the Steam overlay.  I need it to invite friends to play the game.\n\n"
        "## Reproduction\n\n"
        "Launch the game in fullscreen and v-sync turned off.\n"
    )

    result = label_single(client, model, temperature, user_prompt)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
