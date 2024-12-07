#!/usr/bin/env python3

import os
import tomllib
from jinja2 import Environment, FileSystemLoader
from multiprocessing import Pool
import argparse


def render_template(template_info):
    """Render a single Jinja template to the specified output path."""
    template_file, output_file_path = template_info
    template_name = os.path.basename(template_file)
    template_dir = os.path.dirname(template_file)

    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template(template_name)

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_file_path), exist_ok=True)

    # Render and write output
    with open(output_file_path, "w") as f:
        f.write(template.render())


def main(config_file):
    # Get the directory of the config file
    config_dir = os.path.dirname(os.path.abspath(config_file))

    # Parse TOML file using tomllib
    with open(config_file, "rb") as f:
        config = tomllib.load(f)

    # Extract template-output pairs
    template_info = []
    file_pairs = config.get("jinja_static_html_template", [])

    if not isinstance(file_pairs, list):
        raise ValueError("'jinja_static_html_template' must be a list of dictionaries.")

    for pair in file_pairs:
        if not isinstance(pair, dict):
            raise ValueError("Each 'jinja_static_html_template' must be a dictionary with 'template' and 'output' keys.")
        jinja_template_file = pair.get("template")
        output_static_html_file = pair.get("output")
        if not jinja_template_file or not output_static_html_file:
            raise ValueError("Each file pair must specify 'template' and 'output'.")

        # Prepend the config file directory to relative paths
        jinja_template_file = os.path.join(config_dir, jinja_template_file)
        output_static_html_file = os.path.join(config_dir, output_static_html_file)

        template_info.append((jinja_template_file, output_static_html_file))

    # Use multiprocessing to render templates in parallel
    with Pool() as pool:
        pool.map(render_template, template_info)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Render Jinja templates to HTML files based on a TOML configuration."
    )
    parser.add_argument(
        "config_file",
        help="Path to the TOML configuration file.",
    )

    args = parser.parse_args()

    if not os.path.isfile(args.config_file):
        raise FileNotFoundError(f"Configuration file '{args.config_file}' not found.")

    print("Generating html from Jinja templates...")
    
    main(args.config_file)
