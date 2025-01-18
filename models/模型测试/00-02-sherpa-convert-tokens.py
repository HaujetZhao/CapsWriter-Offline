#!/usr/bin/env python3
from pathlib import Path
from typing import Dict

import yaml


def write_tokens(tokens: Dict[int, str]):
    with open("tokens.txt", "w", encoding="utf-8") as f:
        for idx, s in enumerate(tokens):
            f.write(f"{s} {idx}\n")


def main():
    if Path("./tokens.txt").is_file():
        print("./tokens.txt already exists - skipping")
        return

    with open("config.yaml", "r", encoding="utf-8") as stream:
        config = yaml.safe_load(stream)

    tokens = config["token_list"]
    write_tokens(tokens)


if __name__ == "__main__":
    main()
