"""
main.py
--------
CLI entry point for headless pipeline execution (no Streamlit UI).

Usage:
    python main.py --text "Paste article text here"
    python main.py --pdf path/to/article.pdf
    python main.py --url https://example.com/science-article
    python main.py --text-file article.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Science Animation System — headless pipeline runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py --text "Quantum entanglement is..."
  python main.py --text-file article.txt
  python main.py --pdf lecture_notes.pdf
  python main.py --url https://arxiv.org/abs/...
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--text", help="Science article as plain text")
    input_group.add_argument("--text-file", help="Path to a .txt file containing the article")
    input_group.add_argument("--pdf", help="Path to a PDF file")
    input_group.add_argument("--url", help="URL of a science article")

    parser.add_argument(
        "--output-dir",
        default="output",
        help="Base output directory (default: output/)",
    )
    parser.add_argument(
        "--no-social",
        action="store_true",
        help="Skip social media publishing after approval",
    )

    args = parser.parse_args()

    # ── Determine input ────────────────────────────────────────────────────────
    if args.text:
        input_text = args.text
        source_type = "text"
        input_path = None
    elif args.text_file:
        text_path = Path(args.text_file)
        if not text_path.exists():
            print(f"Error: File not found: {args.text_file}", file=sys.stderr)
            sys.exit(1)
        input_text = text_path.read_text(encoding="utf-8")
        source_type = "text"
        input_path = None
    elif args.pdf:
        pdf_path = Path(args.pdf)
        if not pdf_path.exists():
            print(f"Error: PDF not found: {args.pdf}", file=sys.stderr)
            sys.exit(1)
        input_text = str(pdf_path)
        source_type = "pdf"
        input_path = str(pdf_path)
    elif args.url:
        input_text = args.url
        source_type = "url"
        input_path = args.url
    else:
        parser.print_help()
        sys.exit(1)

    # ── Run pipeline ───────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Science Animation System — Pipeline Runner")
    print(f"{'='*60}")
    print(f"  Source type : {source_type}")
    print(f"  Output dir  : {args.output_dir}/")
    print(f"{'='*60}\n")

    from agents.supervisor import run_pipeline

    try:
        final_state = run_pipeline(input_text, source_type, input_path)
    except Exception as exc:
        print(f"\n[ERROR] Pipeline failed: {exc}", file=sys.stderr)
        sys.exit(1)

    # ── Summary ────────────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"  Pipeline Complete!")
    print(f"{'='*60}")

    final_video = final_state.get("final_video_path")
    if final_video:
        print(f"  Final video : {final_video}")
    else:
        print("  Final video : NOT GENERATED (check error log)")

    error_log = final_state.get("error_log", [])
    if error_log:
        print(f"\n  Errors ({len(error_log)}):")
        for msg in error_log:
            print(f"    • {msg}")

    storyboard = final_state.get("storyboard", [])
    scene_summary = ", ".join(
        f"S{s['scene_id']}:{s.get('status','?')}" for s in storyboard
    )
    print(f"\n  Scenes      : {scene_summary}")
    print(f"{'='*60}")
    print(f"\n  Open the Streamlit UI to review and publish:")
    print(f"    streamlit run app.py")
    print()


if __name__ == "__main__":
    main()
