#!/usr/bin/env python3

import meilisearch
import glob
import json

from crawl import chunk_json_path

client = meilisearch.Client("http://localhost:7700", "aSampleMasterKey")

if __name__ == "__main__":
    json_files = glob.glob(chunk_json_path + "*")
    for json_file in json_files:
        chunk_json = open(json_file, encoding="utf-8")
        chunk = json.load(chunk_json)
        client.index("chunks").add_documents(chunk)

    response = client.index("chunks").search("Machine Learning")

    with open("search_results.json", "w", encoding="utf-8") as f:
        json.dump(response, f, ensure_ascii=False, indent=4)
    print(response)
