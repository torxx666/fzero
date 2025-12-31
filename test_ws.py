import asyncio
import websockets
import sys

async def test_connection():
    uri = "ws://localhost:8000/ws/test_client"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected successfully!")
            await websocket.send("ping")
            response = await websocket.recv()
            print(f"Received: {response}")
            print("WebSocket Backend is OK.")
    except Exception as e:
        print(f"Connection failed: {e}")
        print("Make sure the backend is running and port 8000 is exposed.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_connection())
