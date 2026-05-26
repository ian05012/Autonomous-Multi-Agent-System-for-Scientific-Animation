"""
rag/validate_examples.py
------------------------
Validates all LLM-generated Manim examples by actually rendering them
inside the Docker sandbox.

Only examples that successfully render are eligible for RAG indexing.
Results are recorded in rag/examples/validation_results.json.

Usage:
    python rag/validate_examples.py               # validate all unvalidated
    python rag/validate_examples.py --revalidate  # force re-validate all
    python rag/validate_examples.py --report      # show validation report only

Exit code: 0 if all pass, 1 if any fail (useful for CI).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

# ─── Configuration ────────────────────────────────────────────────────────────

EXAMPLES_DIR = Path(__file__).parent / "examples"
RESULTS_FILE = EXAMPLES_DIR / "validation_results.json"
MANIM_IMAGE = os.getenv("MANIM_IMAGE", "manimcommunity/manim:latest")
RENDER_TIMEOUT = 60  # seconds per example (shorter than production: simpler scenes)
RENDER_RESOLUTION = "854,480"  # 480p for validation speed


# ─── Validation result schema ─────────────────────────────────────────────────

class ValidationResult:
    def __init__(
        self,
        filename: str,
        passed: bool,
        error: str = "",
        render_time: float = 0.0,
        validated_at: str = "",
    ):
        self.filename = filename
        self.passed = passed
        self.error = error
        self.render_time = render_time
        self.validated_at = validated_at or datetime.utcnow().isoformat()

    def to_dict(self) -> dict:
        return {
            "filename": self.filename,
            "passed": self.passed,
            "error": self.error,
            "render_time": self.render_time,
            "validated_at": self.validated_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ValidationResult":
        return cls(
            filename=d["filename"],
            passed=d["passed"],
            error=d.get("error", ""),
            render_time=d.get("render_time", 0.0),
            validated_at=d.get("validated_at", ""),
        )


# ─── Load / save results ──────────────────────────────────────────────────────

def load_results() -> dict[str, ValidationResult]:
    """Load existing validation results from disk."""
    if not RESULTS_FILE.exists():
        return {}
    with open(RESULTS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {r["filename"]: ValidationResult.from_dict(r) for r in data}


def save_results(results: dict[str, ValidationResult]) -> None:
    """Persist validation results to disk."""
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(
            [r.to_dict() for r in sorted(results.values(), key=lambda r: r.filename)],
            f,
            indent=2,
            ensure_ascii=False,
        )


# ─── Extract scene class name ─────────────────────────────────────────────────

def _extract_class_name(code: str) -> str | None:
    """Extract the first Scene subclass name from Python code."""
    import re
    match = re.search(r"class\s+(\w+)\s*\(.*Scene.*\)\s*:", code)
    return match.group(1) if match else None


# ─── Render a single example ──────────────────────────────────────────────────

def validate_example(py_file: Path) -> ValidationResult:
    """
    Render a Manim example inside Docker and return a ValidationResult.

    The example is considered valid if:
    - Docker container exits with code 0
    - At least one MP4 file is produced in the workspace
    """
    import time

    code = py_file.read_text(encoding="utf-8")
    class_name = _extract_class_name(code)
    if not class_name:
        return ValidationResult(
            filename=py_file.name,
            passed=False,
            error="Could not find a Scene subclass in the file.",
        )

    start = time.time()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Copy script into workspace
        script_path = Path(tmpdir) / "scene.py"
        script_path.write_text(code, encoding="utf-8")

        # Build Docker command
        cmd = [
            "docker", "run", "--rm",
            "-v", f"{tmpdir}:/workspace",
            "-w", "/workspace",
            MANIM_IMAGE,
            "manim", "scene.py", class_name,
            "--media_dir", "/workspace/media",
            "--format", "mp4",
            "-r", RENDER_RESOLUTION,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=RENDER_TIMEOUT,
            )
            elapsed = round(time.time() - start, 1)

            if result.returncode != 0:
                # Capture useful part of stderr (last 1000 chars)
                stderr = result.stderr[-1000:] if result.stderr else "(no stderr)"
                return ValidationResult(
                    filename=py_file.name,
                    passed=False,
                    error=f"Exit code {result.returncode}. Stderr: {stderr}",
                    render_time=elapsed,
                )

            # Verify MP4 was produced
            mp4_files = list(Path(tmpdir).rglob("*.mp4"))
            if not mp4_files:
                return ValidationResult(
                    filename=py_file.name,
                    passed=False,
                    error="Render succeeded but no MP4 produced.",
                    render_time=elapsed,
                )

            return ValidationResult(
                filename=py_file.name,
                passed=True,
                render_time=elapsed,
            )

        except subprocess.TimeoutExpired:
            elapsed = round(time.time() - start, 1)
            return ValidationResult(
                filename=py_file.name,
                passed=False,
                error=f"Render timed out after {RENDER_TIMEOUT}s.",
                render_time=elapsed,
            )
        except FileNotFoundError:
            return ValidationResult(
                filename=py_file.name,
                passed=False,
                error="Docker not found. Ensure Docker is installed and running.",
            )
        except Exception as exc:
            return ValidationResult(
                filename=py_file.name,
                passed=False,
                error=str(exc),
            )


# ─── Report ───────────────────────────────────────────────────────────────────

def print_report(results: dict[str, ValidationResult]) -> None:
    """Print a human-readable validation report."""
    passed = [r for r in results.values() if r.passed]
    failed = [r for r in results.values() if not r.passed]

    print(f"\n{'='*60}")
    print(f"  Manim Examples Validation Report")
    print(f"{'='*60}")
    print(f"  Total:   {len(results)}")
    print(f"  Passed:  {len(passed)}  ✓")
    print(f"  Failed:  {len(failed)}  ✗")
    print(f"{'='*60}")

    if passed:
        print(f"\n✓ PASSED ({len(passed)}):")
        for r in sorted(passed, key=lambda x: x.filename):
            print(f"  [{r.render_time:.1f}s] {r.filename}")

    if failed:
        print(f"\n✗ FAILED ({len(failed)}):")
        for r in sorted(failed, key=lambda x: x.filename):
            print(f"  {r.filename}")
            print(f"    Error: {r.error[:200]}")

    print(f"\n  RAG-eligible examples: {len(passed)}/{len(results)}")
    print(f"  Results saved to: {RESULTS_FILE}")
    print(f"{'='*60}\n")


# ─── Main ─────────────────────────────────────────────────────────────────────

def run_validation(revalidate: bool = False) -> dict[str, ValidationResult]:
    """Run validation for all example .py files."""
    py_files = sorted(EXAMPLES_DIR.glob("ex_*.py"))

    if not py_files:
        print(f"No example files found in {EXAMPLES_DIR}")
        print("Run the pipeline first to generate examples, or add .py files manually.")
        return {}

    existing_results = load_results() if not revalidate else {}

    results = dict(existing_results)
    to_validate = [f for f in py_files if f.name not in results]

    if not to_validate:
        print(f"All {len(py_files)} examples already validated. Use --revalidate to re-run.")
        return results

    print(f"\nValidating {len(to_validate)} example(s) via Docker...")
    print(f"Using image: {MANIM_IMAGE}")
    print(f"Timeout per example: {RENDER_TIMEOUT}s\n")

    for i, py_file in enumerate(to_validate, start=1):
        print(f"  [{i}/{len(to_validate)}] {py_file.name} ... ", end="", flush=True)
        result = validate_example(py_file)
        results[py_file.name] = result

        if result.passed:
            print(f"✓  ({result.render_time:.1f}s)")
        else:
            short_error = result.error[:80].replace("\n", " ")
            print(f"✗  {short_error}")

        # Save after each file (in case of interruption)
        save_results(results)

    return results


def get_valid_example_files() -> list[Path]:
    """
    Return a list of .py example files that have passed validation.
    Used by build_index.py to filter which examples to index.
    """
    if not RESULTS_FILE.exists():
        return []  # No validation run yet — skip examples in RAG build
    results = load_results()
    return [
        EXAMPLES_DIR / filename
        for filename, result in results.items()
        if result.passed and (EXAMPLES_DIR / filename).exists()
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Validate Manim CE examples by actually rendering them."
    )
    parser.add_argument(
        "--revalidate",
        action="store_true",
        help="Re-validate all examples, ignoring cached results.",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Show validation report from cached results without re-running.",
    )
    args = parser.parse_args()

    if args.report:
        results = load_results()
        if not results:
            print("No validation results found. Run without --report first.")
            sys.exit(1)
        print_report(results)
        sys.exit(0)

    results = run_validation(revalidate=args.revalidate)
    print_report(results)

    # Exit 1 if any failures (useful for CI)
    failed = [r for r in results.values() if not r.passed]
    sys.exit(1 if failed else 0)
