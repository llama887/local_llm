#!/usr/bin/env python3

import asyncio
import websockets
import os
import socket
from langchain.vectorstores import Chroma
from langchain.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from openai import OpenAI  

persist_directory = 'db'  
embedding = OpenAIEmbeddings()
vectordb = Chroma(persist_directory=persist_directory, embedding_function=embedding)

MODEL = "Qwen2.5-1.5B-Instruct-GGUF"
client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

retriever = vectordb.as_retriever(search_kwargs={"k": 2}) 

qa_chain = RetrievalQA.from_chain_type(
    llm=client,  
    chain_type="stuff",
    retriever=retriever,
    return_source_documents=True
)

connected_clients = set()

def find_free_port():
    """Find a free port to avoid conflicts."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def process_llm_response(llm_response):
    """Format the LLM response with sources."""
    result = f"Answer: {llm_response['result']}\n\nSources:\n"
    for source in llm_response["source_documents"]:
        result += f"- {source.metadata['source']}\n"
    return result

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
                try:
                    print(f"Processing RAG query: {message}")

                    llm_response = qa_chain.run(message)

                    response = process_llm_response(llm_response)

                    print(f"Generated response:\n{response}")
                except Exception as e:
                    response = f"Error processing your request: {str(e)}"
                    print(f"Error during RAG processing: {e}")
                
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
            await asyncio.Future()
    except Exception as e:
        print(f"Error starting WebSocket server: {e}")

if __name__ == "__main__":
    asyncio.run(main())