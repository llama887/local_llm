# Updated `chat.py`
import asyncio
import websockets
import os
import socket
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.chains import RetrievalQA
from langchain.llms import OpenAI
import subprocess
from tools import tools
from chromadb.utils import embedding_functions


WINDOWS_LMS_PATH = "/mnt/c/Users/qc_wo/.cache/lm-studio/bin/lms.exe"

persist_directory = 'data/chroma_db'
retriever = None
qa_chain = None

# Check if the database exists
if os.path.exists(persist_directory):
    print(f"Database found at {persist_directory}. Using Chroma retriever.")
    embedding = embedding_functions.DefaultEmbeddingFunction()
    vectordb = Chroma(persist_directory=persist_directory, embedding_function=embedding)
    retriever = vectordb.as_retriever(search_kwargs={"k": 2})
else:
    print(f"Database not found at {persist_directory}. Using Qwen model only.")

client = OpenAI(base_url="http://localhost:1234/v1", api_key="lm-studio")

MODEL = "Llama-3.2-3B-Instruct-4bit"
try:
    try:
        subprocess.run([WINDOWS_LMS_PATH, "load", "llama-3.2-3b-qnn", "-y"])
    except:
        subprocess.run(["lms", "load", "llama-3.2-3b-qnn", "-y"])
    MODEL = "llama-3.2-3b-qnn"
except:
    try:
        subprocess.run([WINDOWS_LMS_PATH, "load", "Llama-3.2-3B-Instruct-4bit", "-y"])
    except:
        subprocess.run(["lms", "load", "Llama-3.2-3B-Instruct-4bit", "-y"])
    MODEL = "Llama-3.2-3B-Instruct-4bit"

if retriever:
    qa_chain = RetrievalQA.from_chain_type(
        llm=client,
        chain_type="stuff",
        retriever=retriever,
        return_source_documents=True
    )

connected_clients = set()
client_states = {}  # To track the state of each connected client

def find_free_port():
    """Find a free port to avoid conflicts."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]

def process_llm_response(llm_response):
    """Format the LLM response with sources."""
    if "source_documents" in llm_response:
        result = f"Answer: {llm_response['result']}\n\nSources:\n"
        for source in llm_response["source_documents"]:
            result += f"- {source.metadata['source']}\n"
    else:
        result = f"Answer: {llm_response}"
    return result

async def stream_response(websocket, text, delay=0.01):
    """Stream response to the WebSocket client character by character."""
    for char in text:
        try:
            await websocket.send(char)
            await asyncio.sleep(delay)
        except websockets.exceptions.ConnectionClosed:
            print("WebSocket connection closed during streaming.")
            return
    try:
        await websocket.send("[END]")
    except websockets.exceptions.ConnectionClosed:
        print("WebSocket connection closed while sending [END].")

async def handle_websocket(websocket, path=None):
    """Handle WebSocket connections."""
    print(f"New WebSocket connection from {websocket.remote_address}, Path: {path}")
    connected_clients.add(websocket)
    client_states[websocket] = {"awaiting_response": False}
    try:
        while True:
            try:
                message = await websocket.recv()
                print(f"Received message: {message}")

                # Ignore heartbeat messages
                if message == "heartbeat":
                    print("Heartbeat received, ignoring.")
                    continue

                # Check if the client is already awaiting a response
                if client_states[websocket]["awaiting_response"]:
                    await websocket.send("Server is still processing your previous request. Please wait.")
                    continue

                client_states[websocket]["awaiting_response"] = True

                if qa_chain:
                    llm_response = qa_chain.run(message)
                    response = process_llm_response(llm_response)
                else:
                    llm_response = client.completions.create(
                        model=MODEL,
                        prompt=message,
                        tools=tools
                    )
                    response = llm_response.choices[0].text.strip()

                print(f"Generated response:\n{response}")
                await stream_response(websocket, response)

            except websockets.exceptions.ConnectionClosed as e:
                if e.code == 1000:
                    print("Client closed the connection normally.")
                elif e.code == 1006:
                    print("Abnormal WebSocket closure. Check client-server compatibility.")
                else:
                    print(f"Connection closed unexpectedly with code {e.code}: {e.reason}")
                break
            except Exception as e:
                print(f"Unhandled error: {e}")
                import traceback
                traceback.print_exc()
                break
            finally:
                client_states[websocket]["awaiting_response"] = False
    finally:
        connected_clients.remove(websocket)
        del client_states[websocket]
        print(f"Connection from {websocket.remote_address} closed")
        print(f"Remaining connected clients: {len(connected_clients)}")

async def main():
    """Main function for starting the WebSocket server."""
    print("Running updated chat.py")
    port = int(os.getenv("PORT", find_free_port()))
    print(f"Starting WebSocket server on ws://localhost:{port}")

    try:
        async with websockets.serve(
            handle_websocket, "localhost", port, ping_interval=20, ping_timeout=10
        ):
            print(f"WebSocket server successfully bound to ws://localhost:{port}")
            await asyncio.Future()
    except Exception as e:
        print(f"Error starting WebSocket server: {e}")

if __name__ == "__main__":
    asyncio.run(main())