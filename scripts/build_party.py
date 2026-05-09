from __future__ import annotations

import argparse
from dataclasses import asdict
from pprint import pprint
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from core.request_parser import parse_build_request


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

    pprint(asdict(build_request), sort_dicts=False)


if __name__ == "__main__":
    main()
    