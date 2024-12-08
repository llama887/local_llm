#!/usr/bin/env python3

import chromadb

def main(add_new):
    # Initialize the ChromaDB client
    client = chromadb.Client()

    # List all collections
    collections = client.list_collections()

    # Print HTTP response headers
    print("Content-Type: text/html")
    print()  # blank line to end headers

    print("<ul>")
    for collection in collections:
        print(f"<li>{collection.name}</li>")
    if add_new:
        print("<li>")
        print("<form>")
        print("<input type=\"text\" name=\"expert\" value=\"New Expert\" onfocus=\this.select()\" required>")
        print("<button type=\"submit\">+</button>")
        print("</form>")
        print("</li>")
    print("</ul>")

if __name__ == "__main__":
    main(True)
