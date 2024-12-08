import difflib
import hashlib
from typing import List, Dict
from tqdm import tqdm  # For progress bars

# Import your ChromaDB and MeiliSearch clients
import chromadb
import meilisearch



def compute_similarity(a: str, b: str) -> float:
    """
    Compute the similarity ratio between two strings.
    """
    return difflib.SequenceMatcher(None, a, b).ratio()

def generate_meilisearch_id(link: str, idx: int) -> int:
    """
    Generate the MeiliSearch document ID based on link and index.
    """
    return hash(link + str(idx))

def clean_duplicate_chunks(
    chroma_client,
    meili_client: meilisearch.Client,
    chroma_collection_name: str = "chunks",
    meili_index_name: str = "chunks",
    similarity_threshold: float = 0.95
):
    """
    Cleans duplicate chunks from both ChromaDB and MeiliSearch based on similarity.
    
    Args:
        chroma_client (ChromaClient): Instance of ChromaDB client.
        meili_client (meilisearch.Client): Instance of MeiliSearch client.
        chroma_collection_name (str): Name of the ChromaDB collection.
        meili_index_name (str): Name of the MeiliSearch index.
        similarity_threshold (float): Threshold above which chunks are considered duplicates.
    """
    
    # Access the ChromaDB collection
    collection = chroma_client.get_collection(chroma_collection_name)
    
    # Fetch all documents from ChromaDB
    # ChromaDB may have pagination; ensure you fetch all documents
    # Assuming ChromaDB's `get` method can fetch all documents
    all_docs = collection.get(
        limit=collection.count(),  # Assuming -1 fetches all documents
        include=["documents", "metadatas", "ids"]
    )
    
    documents = all_docs['documents']
    metadatas = all_docs['metadatas']
    ids = all_docs['ids']
    
    print(f"Fetched {len(documents)} documents from ChromaDB.")

    # Initialize structures to keep track of unique chunks and duplicates
    unique_chunks = []  # List of tuples (id, document, metadata)
    duplicate_ids = []  # IDs of duplicate chunks
    duplicate_meili_ids = []  # MeiliSearch IDs of duplicate chunks

    # Iterate through all documents and identify duplicates
    for i in tqdm(range(len(documents)), desc="Processing chunks"):
        current_doc = documents[i]
        current_meta = metadatas[i]
        current_id = ids[i]
        
        is_duplicate = False
        for unique_doc, _, _ in unique_chunks:
            similarity = compute_similarity(current_doc, unique_doc)
            if similarity >= similarity_threshold:
                is_duplicate = True
                break
        
        if is_duplicate:
            duplicate_ids.append(current_id)
            link = current_meta.get("url", "")
            idx = current_meta.get("chunk_index", 0)
            meili_id = generate_meilisearch_id(link, idx)
            duplicate_meili_ids.append(meili_id)
        else:
            unique_chunks.append((current_doc, current_id, current_meta))
    
    print(f"Identified {len(duplicate_ids)} duplicate chunks.")

    # Delete duplicates from ChromaDB
    if duplicate_ids:
        # ChromaDB's delete method may require a list of IDs
        collection.delete(duplicate_ids)
        print(f"Deleted {len(duplicate_ids)} duplicate chunks from ChromaDB.")
    else:
        print("No duplicates found in ChromaDB to delete.")

    # Delete duplicates from MeiliSearch
    if duplicate_meili_ids:
        meili_index = meili_client.index(meili_index_name)
        # MeiliSearch expects a list of string IDs; convert if necessary
        meili_ids_str = [str(mid) for mid in duplicate_meili_ids]
        meili_index.delete_documents(meili_ids_str)
        print(f"Deleted {len(duplicate_meili_ids)} duplicate chunks from MeiliSearch.")
    else:
        print("No duplicates found in MeiliSearch to delete.")

    print("Deduplication process completed.")

# Example Usage
if __name__ == "__main__":
    # Initialize ChromaDB client
    chroma_client = chromadb.PersistentClient(path="data/chroma_db")

    # Initialize MeiliSearch client
    meili_client = meilisearch.Client("http://localhost:7700", "aSampleMasterKey")

    # Call the deduplication function
    clean_duplicate_chunks(
        chroma_client=chroma_client,
        meili_client=meili_client,
        chroma_collection_name="llms",
        meili_index_name="chunks",
        similarity_threshold=0.95  # Adjust threshold as needed
    )
