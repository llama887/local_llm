#!/usr/bin/env python3
import requests
import time
import chromadb
from langchain.text_splitter import RecursiveCharacterTextSplitter
from bs4 import BeautifulSoup
import subprocess
from openai import OpenAI
import os
from pydantic import BaseModel, Field, ValidationError
from typing import List
import urllib.request
import lxml.html
import json
from urllib.parse import urlparse, parse_qs, quote
import re
import meilisearch

searched_links = set()
max_searched_links_size = 10

data_path = "data/"
os.makedirs(data_path, exist_ok=True)


def try_tpu(client, message, pydantic_model):
    if not hasattr(try_tpu, "tpu_failed"):
        try_tpu.tpu_failed = False
    if not try_tpu.tpu_failed:
        response = client.chat.completions.create(
            model=model_tpu,
            messages=message,
            extra_body={"guided_json": pydantic_model.model_json_schema()},
        )
        raw_data = response.choices[0].message
        try:
            validated_data = pydantic_model.parse_obj(raw_data)
        except ValidationError as e:
            try_tpu.tpu_failed = True
            print(f"The following does not conform to the model:\n{raw_data}")
            print("Switching Models....")
            subprocess.run(["lms", "unload", "--all"])
            subprocess.run(["lms", "load", model_non_tpu, "-y"])
    if try_tpu.tpu_failed:
        response = client.beta.chat.completions.parse(
            model=model_non_tpu,
            messages=message,
            response_format=pydantic_model,
        )
    return response


model_non_tpu = "qwen2.5-1.5b-instruct"
model_tpu = None

WINDOWS_LMS_PATH = "/mnt/c/Users/qc_wo/.cache/lm-studio/bin/lms.exe"
def setup_models():
    available_models = set()
    try:
        lms_ls_output = subprocess.run(["lms", "ls"], stdout=subprocess.PIPE, text=True)
    except:
        lms_ls_output = subprocess.run([WINDOWS_LMS_PATH, "ls"], stdout=subprocess.PIPE, text=True)
    lms_ls_lines = lms_ls_output.stdout.splitlines()
    for line in lms_ls_lines:
        if "/" in line:  # Filter lines that likely contain a model name
            model_name = line.split()[0].split("/")[
                1
            ]  # Take the first element before the first space
            available_models.add(model_name)

    global model_tpu, model_non_tpu

    if not available_models:
        raise Exception("You need model la")
    else:
        print(len(available_models), "available models: ", available_models)

    if "qwen2.5-1.5b-instruct" in available_models:
        model_tpu = "qwen2.5-1.5b-instruct"
        print("USING: qwen2.5-1.5b-instruct")
    else:
        try_tpu.tpu_failed = True
        print("Not using: qwen2.5-1.5b-instruct")


def load_models():
    try: 
        setup_models()
        print("Loading model...")
        try:
            subprocess.run(["lms", "unload", "--all"])
        except: 
            subprocess.run([WINDOWS_LMS_PATH, "unload", "--all"])
        model_to_use = model_non_tpu if try_tpu.tpu_failed else model_tpu
        try:
            subprocess.run(["lms", "load", model_to_use, "-y"])
        except:
            subprocess.run([WINDOWS_LMS_PATH, "load", model_to_use, "-y"])
        print("Using:", model_to_use)
    except Exception as e:
        try_tpu.tpu_failed = True
        print(f"Exception: {e}")


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


def scrape_link(link, topic, client, database_collection, recursive=False):
    meilisearch_client = meilisearch.Client("http://localhost:7700", "aSampleMasterKey")

    global searched_links
    if (link in searched_links) or (len(searched_links) >= max_searched_links_size):
        return
    print(f"Scraping {link}")
    if link in searched_links:
        return
    searched_links.add(link)

    title = extract_title(link)
    print(f"Titling {link} as: {title}")

    class ImportantUrls(BaseModel):
        """For a list of links, pick the most important links to focus on"""

        important_urls: List[str] = Field(
            ..., min_items=3, description="Most important links to focus on next"
        )
        reason_for_decision: str = Field(
            ..., description="A short reason for picking those urls."
        )

    if recursive:
        headers = {"X-Retain-Images": "none", "X-With-Links-Summary": "true"}
    else: 
        headers = {"X-Retain-Images": "none"}
    cleaned_markdown = requests.get(f"https://r.jina.ai/{link}", headers=headers)
    while cleaned_markdown.status_code != 200:
        print(f"Retrying {link} in 30 seconds...")
        time.sleep(30)
        cleaned_markdown = requests.get(f"https://r.jina.ai/{link}", headers=headers)
    if recursive:
        index = cleaned_markdown.text.find("Links/Buttons")
        if index != -1:
            print(f"Searched through: {len(searched_links)}")
            md_links = cleaned_markdown.text[index:]
            # Regular expression to find URLs
            url_pattern = r"https?://[^\s\)]+"
            all_urls = re.findall(url_pattern, md_links)
            domain = urlparse(link).netloc
            domain_matching_urls = [
                url for url in all_urls if urlparse(url).netloc.endswith(domain)
            ]
            messages = [
                {
                    "role": "system",
                    "content": "You are a professional researcher who picks the best links to click on next given a list of all links. You return data strictly in the requested format.",
                },
                {
                    "role": "user",
                    "content": f"Given these urls:\n\n '{domain_matching_urls}'\n\n return a python list that contains the most important urls to explore next given that the topic of interest is {topic}.\n You will justify why you picked these urls.",
                },
            ]
            response = try_tpu(client, messages, ImportantUrls)
            for url in response.choices[0].message.parsed.important_urls:
                if url in searched_links:
                    continue
                if len(searched_links) <= max_searched_links_size:
                    scrape_link(url, topic, client, database_collection, True)

    class ChunkValidation(BaseModel):
        """For the given markdown, determine if it gives additional information related to the topic."""

        answers_the_question: bool = Field(
            ..., description="Whether the text gives additional information related to the topic."
        )
        reason_for_decision: str = Field(
            ..., description="A short justification for rejecting or accepting the text."
        )
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(cleaned_markdown.text)
    invalid_chunk_ids = []
    print("Evaluating chunks...")
    for id, chunk in enumerate(chunks):
        messages = [
            {
                "role": "system",
                "content": "You are a research manager that will strictly evaluate the quality of the text based on the topic. You return data strictly in the requested format."
            },
            # Example 1: Relevant to the topic "Machine Learning"
            {
                "role": "user",
                "content": (
                    "## Example 1\n"
                    "Given the topic 'Machine Learning' and the markdown below, determine if it contains useful information for the topic.\n\n"
                    "```markdown\n"
                    "Machine learning is a branch of artificial intelligence focused on building systems that learn from data. "
                    "These systems use algorithms and statistical models to identify patterns, make predictions, and improve "
                    "performance over time without being explicitly programmed. For instance, neural networks, a core "
                    "technology within machine learning, have been applied in a wide range of fields—from computer vision "
                    "and natural language processing to financial forecasting and drug discovery. By training on large "
                    "datasets, these models can recognize complex patterns that may be difficult or impossible to design "
                    "manually, thereby accelerating innovation and enabling more sophisticated analytics.\n"
                    "```"
                )
            },
            {
                "role": "assistant",
                "content": (
                    "{\"answers_the_question\": true, "
                    "\"reason_for_decision\": \"The text describes key concepts in machine learning, including algorithms, statistical models, neural networks, and their applications, which is clearly relevant to the given topic.\"}"
                )
            },
            # Example 2: Not relevant to the topic "Machine Learning"
            {
                "role": "user",
                "content": (
                    "## Example 2\n"
                    "Given the topic 'Machine Learning' and the markdown below, determine if it contains useful information for the topic.\n\n"
                    "```markdown\n"
                    "In a remote village near the coast, local artisans have developed unique methods of weaving baskets "
                    "and sculpting pottery. Over centuries, these craftspeople have refined their techniques, passing them "
                    "down through generations. The intricate patterns and vibrant dyes reflect cultural traditions and "
                    "historical influences, while the finished products are sold to travelers who appreciate authentic, "
                    "handmade artwork. Local festivals celebrate these crafts, featuring music, dancing, and elaborate "
                    "costumes. Visitors are often fascinated by the combination of artistry and cultural heritage in every "
                    "piece created.\n"
                    "```"
                )
            },
            {
                "role": "assistant",
                "content": (
                    "{\"answers_the_question\": false, "
                    "\"reason_for_decision\": \"The text focuses on traditional craftsmanship and cultural artistry with no mention of data, algorithms, models, or any machine learning concepts.\"}"
                )
            },
            # Example 3: Relevant to the topic "Climate Change"
            {
                "role": "user",
                "content": (
                    "## Example 3\n"
                    "Given the topic 'Climate Change' and the markdown below, determine if it contains useful information for the topic.\n\n"
                    "```markdown\n"
                    "Over the last century, the Earth's average surface temperature has been steadily increasing, driven "
                    "largely by human activities, particularly the combustion of fossil fuels. Rising atmospheric "
                    "concentrations of greenhouse gases like carbon dioxide and methane have led to shifts in climate "
                    "patterns, resulting in more frequent and severe droughts, storms, and heatwaves. Coral reefs are "
                    "bleaching, sea levels are rising, and agricultural yields in many regions are becoming less "
                    "predictable. International organizations such as the IPCC issue regular reports, urging nations to "
                    "reduce greenhouse gas emissions and transition to renewable energy sources to mitigate the worst "
                    "impacts of climate change.\n"
                    "```"
                )
            },
            {
                "role": "assistant",
                "content": (
                    "{\"answers_the_question\": true, "
                    "\"reason_for_decision\": \"The text addresses greenhouse gas emissions, rising temperatures, climate patterns, and environmental consequences, all directly related to climate change.\"}"
                )
            },
            # Example 4: Not relevant to the topic "Climate Change"
            {
                "role": "user",
                "content": (
                    "## Example 4\n"
                    "Given the topic 'Climate Change' and the markdown below, determine if it contains useful information for the topic.\n\n"
                    "```markdown\n"
                    "Modern smartphones integrate cutting-edge processors and high-resolution displays to provide "
                    "consumers with seamless user experiences. From multitasking between applications to enjoying "
                    "immersive gaming and high-quality video streaming, these devices continue to evolve at a rapid "
                    "pace. Manufacturers also focus on user interface design, offering intuitive gestures and AI-driven "
                    "virtual assistants. While battery life remains a challenge, advancements in battery technology and "
                    "fast-charging capabilities ensure that users can stay connected longer. Some models now offer "
                    "innovative camera systems that rival dedicated digital cameras, catering to both casual and "
                    "professional photographers.\n"
                    "```"
                )
            },
            {
                "role": "assistant",
                "content": (
                    "{\"answers_the_question\": false, "
                    "\"reason_for_decision\": \"The text describes smartphones and their features, without mentioning environmental factors, greenhouse gases, policies, or impacts related to climate change.\"}"
                )
            },
            # The actual prompt you will use
            {
                "role": "user",
                "content": f"Given the topic '{topic}' and the markdown below, determine if it contains useful information for the topic.\nYou will justify all of your choices\n\n{chunk}"
            }
        ]
        response = try_tpu(client, messages, ChunkValidation)
        if not response.choices[0].message.parsed.answers_the_question:
            invalid_chunk_ids.append(id)

    print("Deleting invalid chunks...")
    chunks = [item for id, item in enumerate(chunks) if id not in invalid_chunk_ids]

    # Split the document into chunks using LangChain's RecursiveTextSplitter
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(cleaned_markdown.text)
    # write_chunks(link, chunks)

    # Store each chunk
    for idx, chunk in enumerate(chunks):
        chunk_metadata = {
            "url": link,
            "chunk_index": idx,
            "total_chunks": len(chunks),
        }

        chunk_dict = {"id": hash(link + str(idx)), "data": chunk}
        chunk_dict.update(chunk_metadata)
        meilisearch_client.index("chunks").add_documents(chunk_dict)

        # Add chunk to the collection with metadata and chunk-specific ID
        database_collection.add(
            documents=[chunk],
            metadatas=[chunk_metadata],
            ids=[f"{link}_{idx}"],  # Unique ID combining link and chunk index
        )

        # Notify the client about progress
        print(f"Stored chunk {idx+1}/{len(chunks)} for {link} in ChromaDB")


def process_search_results(search_query, topic, client, database_name):
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

    db_client = chromadb.PersistentClient(path="data/chroma_db")
    database_name.replace(" ", "_")
    collection = db_client.get_or_create_collection(f"{database_name}")

    for link in valid_links[:5]:
        scrape_link(link, topic, client, collection)


def main(topic, database_name):
    load_models()
    client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

    class QuerySchema(BaseModel):
        """Expects a list of queries and a topic summary phrase"""

        queries: List[str] = Field(..., min_items=1, max_items=10)

    messages = [
        {
            "role": "system",
            "content": "You are a research assistant that focuses on generating search queries that are important for further exploring a topic. You return data strictly in the requested format.",
        },
        {
            "role": "user",
            "content": f"Given the topic '{topic}' create a Python list of Google search queries that would help you to learn more about it.",
        },
    ]

    response = try_tpu(client, messages, QuerySchema)

    queries = response.choices[0].message.parsed.queries
    print(queries)
    for q in queries:
        print(f"Searching {q}")
        process_search_results(q, topic, client, database_name)
    try:
        subprocess.run(["lms", "unload", "--all"])
    except Exception as e:
        subprocess.run([WINDOWS_LMS_PATH, "unload", "--all"])

def set_max_link_size(params):
    global max_searched_links_size
    max_links = params.get("max_links", ["10"])[0]
    max_searched_links_size = int(max_links)


if __name__ == "__main__":
    # Get the query string from environment
    query_str = os.environ.get("QUERY_STRING", "")

    # Parse the query string
    params = parse_qs(query_str)
    topic = params.get("topic", ["Machine Learning"])[0]
    database_name = params.get("database_name", ["Machine_Learning"])[0]
    set_max_link_size(params)

    main(topic, database_name)
