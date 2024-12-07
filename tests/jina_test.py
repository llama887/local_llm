import requests
import urllib.parse

reader_counter = 0
reader_error = 0
segment_counter = 0
segment_error = 0

while True:
    # Send a request to get a random page from the main namespace
    response = requests.get('https://en.wikipedia.org/w/api.php', params={
        'action': 'query',
        'format': 'json',
        'list': 'random',
        'rnnamespace': 0,  # Only return pages from the main namespace (article pages)
        'rnlimit': 1  # Adjust the number of random pages you want
    })

    # Extract the page title
    data = response.json()
    page_title = data['query']['random'][0]['title']

    # Properly encode the title for the URL
    encoded_title = urllib.parse.quote(page_title)

    # Build the URL with the encoded title
    page_url = f"https://en.wikipedia.org/wiki/{encoded_title}"

    # Send the request to the r.jina.ai URL
    response = requests.get(f"https://r.jina.ai/{page_url}")

    # Check if the request was successful
    if response.status_code != 200:
        print(f"Failed to get data: {response}")
        reader_error += 1
    else:
        last_successful = response.text
        # Increment the successful request counter
        reader_counter += 1
        print(f"{reader_counter} successful reader requests, {reader_error} reader errors")

    # Segment request processing
    if last_successful:
        url = 'https://segment.jina.ai/'
        headers = {
            'Content-Type': 'application/json'
        }
        data = {
            "content": last_successful,
            "return_chunks": True,
            "max_chunk_length": 1000,
            "return_tokens": True
        }

        s_response = requests.post(url, headers=headers, json=data)
        
        # Check if the segment request was successful
        if s_response.status_code != 200:
            segment_error += 1
            print(f"Failed to get segment: {s_response}.")
        else:
            segment_counter += 1
            print(f"{segment_counter} successful segment requests, {segment_error} segment errors")
