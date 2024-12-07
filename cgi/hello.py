#!/usr/bin/env python3
import os
from urllib.parse import parse_qs

# Get the query string from environment
query_str = os.environ.get("QUERY_STRING", "")

# Parse the query string
params = parse_qs(query_str)
name = params.get("name", [""])[0]

# Print HTTP response headers
print("Content-Type: text/html")
print()  # blank line to end headers

# Print the response HTML
if name.strip():
    print(f"<h2>Hello, {name}!</h2>")
else:
    print("<h2>Hello, stranger!</h2>")
