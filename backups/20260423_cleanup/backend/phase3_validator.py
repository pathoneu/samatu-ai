"""
Phase 3 — Validator.
Validates Phase 2 results against training ratios.
"""
import json
import pathlib
from dotenv import load_dotenv
from anthropic import Anthropic
from vision_tools import VALIDATOR_TOOL

load_dotenv(pathlib.Path(__file__).parent / ".env")

VISION_MODEL = "claude-opus-4-7"
_client: Anthropic | None = None

_PROMPT_PATH = pathlib.Path(__file__).parent / "prompts" / "phase3_validator.txt"
_TRAINING_PATH = pathlib.Path(__file__).parent / "training_dataset.json"


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


def _load_training() -> dict:
    return json.loads(_TRAINING_PATH.read_text(encoding="utf-8"))


def phase3_validate(
    merged_quantities: dict,
    phase1: dict,
) -> dict:
    """
    Validate Phase 2 merged quantities.
    Returns validated_quantities, warnings, confidence_level, similar_projects.
    """
    client = _get_client()
    training = _load_training()
    prompt_template = _PROMPT_PATH.read_text(encoding="utf-8")

    project_class = phase1.get("sudetingumo_klase", "medium_house")
    ratios_for_class = training.get("aggregated_ratios_by_class", {}).get(project_class, {})

    prompt = prompt_template.format(
        phase2_results=json.dumps(merged_quantities, indent=2, ensure_ascii=False),
        phase1_results=json.dumps(phase1, indent=2, ensure_ascii=False),
        training_data=json.dumps(training.get("aggregated_ratios_by_class", {}), indent=2, ensure_ascii=False),
        project_class=project_class,
        expected_ratios_for_this_class=json.dumps(ratios_for_class, indent=2, ensure_ascii=False),
    )

    for attempt in range(3):
        try:
            response = client.messages.create(
                model=VISION_MODEL,
                max_tokens=4096,
                tools=[VALIDATOR_TOOL],
                tool_choice={"type": "tool", "name": "validate_and_finalize"},
                messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
            )
            for block in response.content:
                if block.type == "tool_use":
                    return dict(block.input)
            raise ValueError("Validator did not call tool")
        except Exception as exc:
            if attempt == 2:
                raise
            import time
            time.sleep(2 ** attempt)

    raise ValueError("Phase 3: all retries failed")
