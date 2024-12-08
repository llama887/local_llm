import chromadb

# Create a persistent client
client = chromadb.PersistentClient(path="server/data/chroma_db")  # Replace with your actual path

# List all collections
collections = client.list_collections()

# Print the names of all collections
for collection in collections:
    print(collection.name)