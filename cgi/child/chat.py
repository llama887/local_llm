#!/usr/bin/env python3

import asyncio
import websockets
import os
import sys
import socket

connected_clients = set()

def find_free_port():
    """Find a free port to avoid conflicts."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

async def handle_websocket(websocket, path=None):
    """Handle WebSocket connections."""
    print(f"New WebSocket connection from {websocket.remote_address}, Path: {path}")
    connected_clients.add(websocket)
    try:
        async for message in websocket:
            print(f"Received: {message}")
            if message == "heartbeat":
                response = "heartbeat acknowledged"
                print(f"Responding to heartbeat: {response}")
                await websocket.send(response)
            else:
                response = f"Echo: {message}"
                print(f"Sending response: {response}")
                await websocket.send(response)
    except websockets.exceptions.ConnectionClosed as e:
        print(f"Connection closed: {e}")
    except Exception as e:
        print(f"Unhandled error: {e}")
        import traceback
        traceback.print_exc()
        await websocket.close(code=1011, reason="Internal server error")
    finally:
        connected_clients.remove(websocket)
        print(f"Connection from {websocket.remote_address} closed")
        print(f"Remaining connected clients: {len(connected_clients)}")

async def main():
    """Main function for starting the WebSocket server."""
    print("Running updated chat.py")
    port = int(os.getenv("PORT", find_free_port()))
    print(f"Starting WebSocket server on ws://localhost:{port}")

    try:
        async with websockets.serve(handle_websocket, "localhost", port):
            print(f"WebSocket server successfully bound to ws://localhost:{port}")
            await asyncio.Future()  # Run forever
    except Exception as e:
        print(f"Error starting WebSocket server: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())