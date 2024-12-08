#!/usr/bin/env python3

import meilisearch
import json
from urllib.parse import parse_qs
import os

client = meilisearch.Client("http://localhost:7700", "aSampleMasterKey")
# Print HTTP response headers
print("Content-Type: text/html")
print()  # blank line to end headers

if __name__ == "__main__":
    # Get the query string from environment
    query_str = os.environ.get("QUERY_STRING", "")
    # Parse the query string

    params = parse_qs(query_str)
    search_query = params.get("search_query", [""])[0]

    response = client.index("chunks").search(search_query)

    with open("search_results.json", "w", encoding="utf-8") as f:
        json.dump(response, f, ensure_ascii=False, indent=4)

    print("<h1> DONE <h1>")
