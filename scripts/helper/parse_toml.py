#!/usr/bin/env python3

import argparse
import tomllib
import sys

def parse_toml(toml_file, key_path):
    try:
        with open(toml_file, "rb") as f:
            config = tomllib.load(f)

        # Traverse the key path to get the desired value
        keys = key_path.split(".")
        value = config
        for key in keys:
            if key not in value:
                raise KeyError(f"Key '{key}' not found in the TOML file.")
            value = value[key]

        print(value)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse a TOML file.")
    parser.add_argument("toml_file", help="Path to the TOML file.")
    parser.add_argument("key_path", help="Dot-separated path to the key (e.g., 'server.directory').")

    args = parser.parse_args()
    parse_toml(args.toml_file, args.key_path)
