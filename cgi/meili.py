#!/usr/bin/env python3

import meilisearch
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
    search_query = params.get("search", [""])[
        0
    ]  # Adjusted to match form input "search"
    num_results = int(params.get("results", [10])[0])

    # Search Meilisearch index
    try:
        response = client.index("chunks").search(search_query)
    except:
        response = {}
    hits = response.get("hits", [])
    num_results = min(len(hits), num_results)

    # HTML output
    print("<!DOCTYPE html>")
    print("<html lang='en'>")
    print("<head>")
    print("<meta charset='UTF-8'>")
    print("<meta name='viewport' content='width=device-width, initial-scale=1.0'>")
    print("<title>Search Results</title>")
    print("<style>")
    print("body { font-family: Arial, sans-serif; margin: 20px; }")
    print(
        ".chunk { margin-bottom: 20px; border: 1px solid #ccc; padding: 10px; border-radius: 5px; }"
    )
    print(".chunk-header { font-weight: bold; cursor: pointer; }")
    print(".chunk-data { display: none; margin-top: 10px; }")
    print("</style>")
    print("<script>")
    print(
        """
        function toggleData(id) {
            const dataDiv = document.getElementById(id);
            const rawDiv = document.getElementById(`${id}-raw`);
            const isVisible = dataDiv.style.display === "block";
            dataDiv.style.display = isVisible ? "none" : "block";

            // Render Markdown if showing for the first time
            if (!isVisible && rawDiv) {
                const rawText = rawDiv.textContent;
                const renderedHTML = parseMarkdown(rawText);
                dataDiv.innerHTML = renderedHTML;
            }
        }

        function parseMarkdown(markdown) {
            let html = markdown;

            html = html.replace(/^[-]{3,}$/gm, "<hr>");
            // Headings
            html = html.replace(/^### (.+)$/gm, "<h3>$1</h3>");
            html = html.replace(/^## (.+)$/gm, "<h2>$1</h2>");
            html = html.replace(/^# (.+)$/gm, "<h1>$1</h1>");

            // Bold
            html = html.replace(/\\*\\*(.+?)\\*\\*/g, "<strong>$1</strong>");

            // Italic
            html = html.replace(/\\*(.+?)\\*/g, "<em>$1</em>");

            // Links
            html = html.replace(/\\[(.+?)\\]\\((.+?)\\)/g, '<a href="$2">$1</a>');

            // Unordered lists
            html = html.replace(/^\\* (.+)$/gm, "<ul><li>$1</li></ul>");
            html = html.replace(/<\/ul>\\s*<ul>/g, ""); // Merge consecutive lists

            return html;
        }
    """
    )
    print("</script>")
    print("</head>")
    print("<body>")
    print("<h1>Search Results</h1>")
    print(f"<h3>Displaying {num_results} Documents For: {search_query}</h2>")

    # Generate dropdowns for each chunk
    for idx in range(num_results):
        chunk_id = f"chunk-{idx}"  # Unique ID for each chunk
        result = hits[idx]
        print(f"<div class='chunk'>")
        print(f"<div class='chunk-header' onclick='toggleData(\"{chunk_id}\");'>")
        print(
            f"Chunk ({result['chunk_index']} of {result['total_chunks']}) - <a href='{result['url']}' target='_blank'>{result['url']}</a>"
        )
        print(f"</div>")
        print(
            f"<div id='{chunk_id}-raw' style='display: none;'>{result['data']}</div>"
        )  # Hidden raw data for Markdown parsing
        print(f"<div id='{chunk_id}' class='chunk-data'></div>")
        print(f"</div>")

    print("</body>")
    print("</html>")
