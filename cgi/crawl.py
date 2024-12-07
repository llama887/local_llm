#!/usr/bin/env python3
import requests
import time
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from bs4 import BeautifulSoup
import sys
import openai
from openai import OpenAI
import os
from pydantic import BaseModel, constr
from typing import List
import urllib.request
import lxml.html
import json
from urllib.parse import urlparse, parse_qs, quote

searched_links = set()

data_path = "data/"
chunk_json_path = data_path + "chunks_json/"
os.makedirs(data_path, exist_ok=True)
os.makedirs(chunk_json_path, exist_ok=True)


def extract_title(link):
    try:
        response = requests.get(link)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string if soup.title else "No Title Found"
        return title.strip()
    except Exception as e:
        return f"Error: {e}"


def write_chunks(link, chunks):
    with open("output_chunks.md", "w", encoding="utf-8") as md_file:
        for i, chunk in enumerate(chunks, start=1):
            md_file.write(f"## Chunk {i}\n\n")
            md_file.write(chunk + "\n\n")
            md_file.write("---\n\n")
    print(f"Finished loading chunks for {link}")


def process_search_results(search_query, database_title):
    valid_links = []
    encoded_query = quote(search_query)
    print("Getting valid links....")
    with urllib.request.urlopen(
        f"https://www.google.com/search?q={encoded_query}"
    ) as connection:
        content = connection.read()
    dom = lxml.html.fromstring(content)

    invalid_substrings = set(
        [
            "support",
            "accounts",
            "map",
            "facebook",
            "twitter",
            "instagram",
            "linkedIn",
            "pinterest",
            "snapchat",
            "tiktok",
            "youtube",
            "whatsapp",
            "geeksforgeeks",
        ]
    )
    for link in dom.xpath("//a/@href"):
        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query)
        cleaned_link = (
            query_params["q"][0]
            if "q" in query_params and query_params["q"][0].startswith("https")
            else None
        )

        if cleaned_link and not any(
            substring in cleaned_link for substring in invalid_substrings
        ):
            valid_links.append(cleaned_link)

    client = chromadb.PersistentClient(path=data_path)
    collection = client.get_or_create_collection(f"{database_title.replace(' ', '_')}")

    for link in valid_links[:1]:
        print(f"Scraping {link}")

        global searched_links
        if link in searched_links:
            continue
        searched_links.add(link)

        title = extract_title(link)
        print(f"Titling {link} as: {title}")

        headers = {"X-Retain-Images": "none", "X-With-Links-Summary": "true"}
        cleaned_markdown = requests.get(f"https://r.jina.ai/{link}", headers=headers)
        while cleaned_markdown.status_code != 200:
            print(f"Retrying {link} in 30 seconds...")
            time.sleep(30)
            cleaned_markdown = requests.get(
                f"https://r.jina.ai/{link}", headers=headers
            )

        # Split the document into chunks using LangChain's RecursiveTextSplitter
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000, chunk_overlap=200
        )
        chunks = text_splitter.split_text(cleaned_markdown.text)
        # write_chunks(link, chunks)

        # Store each chunk
        for idx, chunk in enumerate(chunks):
            chunk_metadata = {
                "url": link,
                "chunk_index": idx,
                "total_chunks": len(chunks),
            }

            chunk_dict = {"data": chunk}
            chunk_dict.update(chunk_metadata)
            chunk_json = json.dumps(chunk_dict, indent=4)

            with open(chunk_json_path + f"{title}_{idx}.json", "w") as outfile:
                outfile.write(chunk_json)

            # Add chunk to the collection with metadata and chunk-specific ID
            collection.add(
                documents=[chunk],
                metadatas=[chunk_metadata],
                ids=[f"{link}_{idx}"],  # Unique ID combining link and chunk index
            )

            # Notify the client about progress
            print(f"Stored chunk {idx+1}/{len(chunks)} for {link} in ChromaDB")


def main(topic):
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    class QuerySchema(BaseModel):
        """Expects a list of queries and a topic summary phrase"""

        one_to_five_word_topic_summary: constr(min_length=3, max_length=63)
        queries: List[str]

    messages = [
        {
            "role": "system",
            "content": "You are a research assistant that focuses on generating search queries that are important for further exploring a topic. You return data strictly in the requested format.",
        },
        {
            "role": "user",
            "content": f"Given the topic '{topic}', create a short 1 to 5 word phrase to summarize it and create a Python list of Google search queries that would help you to learn more about it.",
        },
    ]

    response = client.beta.chat.completions.parse(
        model="local-model", messages=messages, response_format=QuerySchema
    )

    queries = response.choices[0].message.parsed.queries
    n_queries = len(queries)
    summary_phrase = response.choices[0].message.parsed.one_to_five_word_topic_summary
    print(queries, summary_phrase)
    for i, q in enumerate(queries):
        print(f"\n\nSearching query ({i}/{n_queries}): {q}")
        process_search_results(q, "Artificial_Intelligence")


if __name__ == "__main__":
    # Print HTTP response headers
    print("Content-Type: text/html")
    print()  # blank line to end headers

    # Get the query string from environment
    query_str = os.environ.get("QUERY_STRING", "")

    # Parse the query string
    params = parse_qs(query_str)
    topic = params.get("topic", [""])[0]
    topic = topic if topic else "Machine Learning"
    main(topic)
