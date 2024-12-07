#!/usr/bin/env python3

import os
import tomllib
from multiprocessing import Pool
import argparse

def delete_file(file_path):
    """Delete a single file specified by the file path."""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted: {file_path}")
        else:
            print(f"File not found, skipping: {file_path}")
    except Exception as e:
        print(f"Error deleting {file_path}: {e}")

def main(config_file):
    # Get the directory of the config file
    config_dir = os.path.dirname(os.path.abspath(config_file))

    # Parse TOML file using tomllib
    with open(config_file, "rb") as f:
        config = tomllib.load(f)

    # Extract output file paths
    output_files = []
    file_pairs = config.get("jinja_static_html_template", [])

    if not isinstance(file_pairs, list):
        raise ValueError("'jinja_static_html_template' must be a list of dictionaries.")

    for pair in file_pairs:
        if not isinstance(pair, dict):
            raise ValueError("Each 'jinja_static_html_template' must be a dictionary with 'template' and 'output' keys.")
        output_static_html_file = pair.get("output")
        if not output_static_html_file:
            raise ValueError("Each file pair must specify 'output'.")

        # Prepend the config file directory to relative paths
        output_static_html_file = os.path.join(config_dir, output_static_html_file)
        output_files.append(output_static_html_file)

    # Use multiprocessing to delete files in parallel
    with Pool() as pool:
        pool.map(delete_file, output_files)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Delete files specified in the output paths of a TOML configuration."
    )
    parser.add_argument(
        "config_file",
        help="Path to the TOML configuration file.",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.config_file):
        raise FileNotFoundError(f"Configuration file '{args.config_file}' not found.")

    print("Deleting files specified in the configuration...")
    
    main(args.config_file)
