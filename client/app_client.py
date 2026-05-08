import asyncio
import websockets


async def main():
    uri = "ws://localhost:8001/ws"

    async with websockets.connect(uri) as websocket:
        while True:
            data = await websocket.recv()
            print(data)


asyncio.run(main())