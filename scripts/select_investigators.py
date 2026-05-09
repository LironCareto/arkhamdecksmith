from __future__ import annotations

import argparse
from dataclasses import asdict
from pprint import pprint
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.request_parser import parse_build_request
from core.investigator_selector import select_investigators


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--request",
        type=str,
        required=True,
        help="Natural-language deckbuilding request.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    build_request = parse_build_request(args.request)

    investigators = select_investigators(build_request)

    print("\n=== BUILD REQUEST ===\n")
    pprint(asdict(build_request), sort_dicts=False)

    print("\n=== SELECTED INVESTIGATORS ===\n")

    for investigator in investigators:
        pprint(asdict(investigator), sort_dicts=False)
        print()


if __name__ == "__main__":
    main()