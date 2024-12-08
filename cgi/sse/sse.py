#!/usr/bin/env python3

import sys
import datetime
import time

# Set the content type for SSE
print("Content-Type: text/event-stream")
print("Cache-Control: no-cache")
print("Connection: keep-alive")
print("")  # Blank line to end headers

# Flush headers
sys.stdout.flush()

for i in range(1, 10):
    # Get the current time
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Send data in SSE format
    print(f"data: {now}\n")

    # Flush the output buffer to ensure data is sent immediately
    sys.stdout.flush()

    # Sleep for 5 seconds before sending the next message
    time.sleep(1)
