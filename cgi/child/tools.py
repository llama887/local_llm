

import requests
import time
import urllib.request
import lxml.html
from urllib.parse import urlparse, parse_qs, quote
from langchain.text_splitter import RecursiveCharacterTextSplitter
import numpy as np
import faiss

import tensorflow_hub as hub
import numpy as np

# Load the Universal Sentence Encoder model
use_model = hub.load("https://tfhub.dev/google/universal-sentence-encoder/4")

def embed_sentences(sentences):
    # sentences should be a list of strings
    embeddings = use_model(sentences)
    return np.array(embeddings)  # Convert to NumPy array for convenience

tools = [
    {
        "type": "function",
        "function": {
            "name": "google_search",
            "description": "Pass the users prompt and generate a google search query that will help you related information if needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "search_query": {
                        "type": "string",
                        "description": "A query that will help you answer the users question.",
                    },
                    "user_question": {
                        "type": "string",
                        "description": "The users question",
                    },
                },
                "required": ["search_query", "user_question"],
            },
        },
    },
]

def google_search(search_query: str, user_question: str)-> str:
    print(f"Searching for {search_query}")
    valid_links = []
    encoded_query = quote(search_query)
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
            "reddit",
            "google",
        ]
    )
    valid_links_max = 3
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
            if len(valid_links) >= valid_links_max:
                break
    if not valid_links or len(valid_links) < 1:
        return ""
    chunks = []
    for link in valid_links:
        print(f"Scraping {link}")
        headers = {"X-Retain-Images": "none"}
        cleaned_markdown = requests.get(f"https://r.jina.ai/{link}", headers=headers)
        while cleaned_markdown.status_code != 200:
            print(f"Retrying {link} in 15 seconds...")
            time.sleep(15)
            cleaned_markdown = requests.get(f"https://r.jina.ai/{link}", headers=headers)
        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
        chunks.extend(text_splitter.split_text(cleaned_markdown.text))
    if len(chunks) < 3:
        print(len(chunks))
        return "".join(f"Snippet #{id}: {chunk}\n\n" for id, chunk in enumerate(chunks))

    # Compute embeddings for all chunks
    chunk_embeddings = embed_sentences(chunks)

    # Normalize embeddings for cosine similarity
    chunk_embeddings = chunk_embeddings / np.linalg.norm(chunk_embeddings, axis=1, keepdims=True)
        # Determine the dimensionality from the embeddings
    embedding_dim = chunk_embeddings.shape[1]

    # Initialize a FAISS index for Inner Product (suitable for cosine similarity with normalized vectors)
    index = faiss.IndexFlatIP(embedding_dim)

    # Add the normalized chunk embeddings to the index
    index.add(chunk_embeddings.astype(np.float32))

    # Encode the query
    query_embedding = embed_sentences([user_question])
    
    # Normalize the query embedding
    query_embedding = query_embedding / np.linalg.norm(query_embedding, axis=1, keepdims=True)
        
    k = 3  # Number of top chunks to retrieve

    # Perform similarity search
    distances, indices = index.search(query_embedding.astype(np.float32), k)

    # Retrieve the top chunks and their scores
    top_chunks = [chunks[idx] for idx in indices[0]]  # `chunks` is the original list of text chunks
    print(f"Length: {len(top_chunks)}")
    return "".join(f"Snippet #{id}: {chunk}\n\n" for id, chunk in enumerate(top_chunks))

if __name__ == "__main__":
    print(google_search("Reinforcement Learning in Robotics", "How is reinforcement learning used in robotics?"))
    print("End")