import asyncio
import json
import random
import time
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
import uvicorn
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Start the background broadcast task
    task = asyncio.create_task(broadcast_market_data())
    print("Market streamer background task started.")
    yield
    # Shutdown: Cancel the task
    task.cancel()
    print("Market streamer background task stopped.")

app = FastAPI(lifespan=lifespan)

# =========================
# Connected Clients
# =========================
connected_clients = set()


# =========================
# Market State
# =========================
market_state = {
    "symbol": "GOLDM26",
    "last_price": 95000.0,
}

# =========================
# Generate OHLCV Candle
# =========================
def generate_ohlcv():
    last_close = market_state["last_price"]

    open_price = last_close

    move = random.uniform(-150, 150)

    close_price = open_price + move

    high_price = max(open_price, close_price) + random.uniform(0, 80)
    low_price = min(open_price, close_price) - random.uniform(0, 80)

    volume = random.randint(10, 500)

    market_state["last_price"] = close_price

    candle = {
        "type": "ohlcv",
        "symbol": market_state["symbol"],
        "timestamp": int(time.time()),
        "datetime": datetime.now().isoformat(),
        "open": round(open_price, 2),
        "high": round(high_price, 2),
        "low": round(low_price, 2),
        "close": round(close_price, 2),
        "volume": volume,
    }

    return candle

# =========================
# Broadcast To Clients
# =========================
async def broadcast_market_data():
    print("Broadcast loop started")
    while True:
        try:
            data = generate_ohlcv()
            message = json.dumps(data)

            disconnected = []

            for client in connected_clients:
                try:
                    await client.send_text(message)
                except Exception:
                    disconnected.append(client)

            # Remove dead connections
            for client in disconnected:
                connected_clients.remove(client)

            print(f"Broadcasted: {data}")

            # 1 candle every second
            await asyncio.sleep(1)

        except Exception as e:
            print("Broadcast Error:", e)
            await asyncio.sleep(1)

# =========================
# Startup Event
# =========================
# Lifespan handles startup/shutdown now

# =========================
# Health Check
# =========================
from fastapi.responses import FileResponse
import os

# =========================
# Dashboard Route
# =========================
@app.get("/")
def home():
    # Path to index.html in the client directory
    client_dir = os.path.join(os.path.dirname(__file__), "..", "client")
    index_path = os.path.join(client_dir, "index.html")
    return FileResponse(index_path)

# =========================
# WebSocket Endpoint
# =========================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    connected_clients.add(websocket)

    print("Client Connected")

    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()

    except WebSocketDisconnect:
        print("Client Disconnected")
        connected_clients.remove(websocket)

    except Exception as e:
        print("WebSocket Error:", e)

        if websocket in connected_clients:
            connected_clients.remove(websocket)

# =========================
# Run Server
# =========================
if __name__ == "__main__":
    uvicorn.run(
        "app_streamer:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )