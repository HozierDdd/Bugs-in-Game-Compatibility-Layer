"""
Pipeline main entry point.

Usage:
    # Run the full pipeline (step 0 -> 7)
    python run_pipeline.py

    # Run only specific steps
    python run_pipeline.py --steps 0 1
    python run_pipeline.py --steps 3
    python run_pipeline.py --steps 7
"""

import argparse
import sys
import time
from src.utils.datetime_utils import now_utc_iso

# Steps defined in dependency order
STEPS: dict[int, tuple[str, object]] = {}

def _load_steps() -> None:
    """Import step modules lazily to avoid loading everything at startup."""
    from src.steps import (
        step0_config,
        step1_coverage,
        step2_protondb,
        step3_github,
        step4_master_summary,
        step5_temporal_layering,
        step6_appid_validation,
        step7_cross_platform_mentions,
        step8_yearly_mentions,
        step9_per_game_mentions,
    )
    STEPS.update({
        0: ("step0_config",                   step0_config.run),
        1: ("step1_coverage",                 step1_coverage.run),
        2: ("step2_protondb",                 step2_protondb.run),
        3: ("step3_github",                   step3_github.run),
        4: ("step4_master_summary",           step4_master_summary.run),
        5: ("step5_temporal_layering",        step5_temporal_layering.run),
        6: ("step6_appid_validation",         step6_appid_validation.run),
        7: ("step7_cross_platform_mentions",  step7_cross_platform_mentions.run),
        8: ("step8_yearly_mentions",          step8_yearly_mentions.run),
        9: ("step9_per_game_mentions",        step9_per_game_mentions.run),
    })


def run_steps(step_ids: list[int]) -> None:
    _load_steps()
    missing = [s for s in step_ids if s not in STEPS]
    if missing:
        print(f"[ERROR] Unknown step number(s): {missing}, valid numbers: {sorted(STEPS)}", file=sys.stderr)
        sys.exit(1)

    print("=== ProtonDB x GitHub Analysis Pipeline ===")
    print(f"Start time: {now_utc_iso()}")
    print(f"Steps scheduled to run: {step_ids}")
    print()

    total_start = time.perf_counter()
    for step_id in step_ids:
        name, func = STEPS[step_id]
        step_start = time.perf_counter()
        try:
            func()
        except Exception as e:
            print(f"\n[FATAL] Step {step_id} ({name}) failed: {e}", file=sys.stderr)
            raise
        elapsed = time.perf_counter() - step_start
        print(f"  ✓ Step {step_id} done in {elapsed:.1f}s\n")

    total_elapsed = time.perf_counter() - total_start
    print(f"=== All steps complete, total time {total_elapsed:.1f}s ===")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ProtonDB x GitHub role divergence analysis pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_pipeline.py              # Run all steps (0-9)
  python run_pipeline.py --steps 0 1  # Run only step0 and step1
  python run_pipeline.py --steps 3    # Run only step3 (requires step1/step2 first)
  python run_pipeline.py --steps 5    # Run only step5 (requires step4 first)
  python run_pipeline.py --steps 6    # Run only step6 (requires step3 first, needs network)
  python run_pipeline.py --steps 7    # Run only step7 (requires step1/step3 first)
  python run_pipeline.py --steps 8    # Run only step8 (requires step1/step3/step7 first)
  python run_pipeline.py --steps 9    # Run only step9 (requires step1/step3/step7 first)
        """,
    )
    parser.add_argument(
        "--steps",
        nargs="+",
        type=int,
        metavar="N",
        help="Step numbers to run (0-9); runs all by default",
    )
    args = parser.parse_args()

    step_ids = args.steps if args.steps else [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    run_steps(step_ids)


if __name__ == "__main__":
    main()
