#!/usr/bin/env python3
import os
from urllib.parse import parse_qs
from crawl import scrape_link, load_models
import subprocess
import chromadb
from openai import OpenAI


if __name__ == "__main__":
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    load_models()
    # Get the query string from environment
    query_str = os.environ.get("QUERY_STRING", "")
    print(f"QUERY STRING:{query_str}")
    # Parse the query string
    params = parse_qs(query_str)
    url = params.get("url", [""])[0]
    topic = params.get("topic", [""])[0]
    database_name = params.get("database_name", [""])[0]
    print(f"\nurl:{url}, topic:{topic}, database_name:{database_name}")

    db_client = chromadb.PersistentClient(path="data/chroma_db")
    collection = db_client.get_or_create_collection(f"{database_name}")

    scrape_link(url, topic, client, collection, True)
