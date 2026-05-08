import asyncio
import json
import random
import time
import httpx
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
# Configuration
# =========================
CONFIG = {
    # Replace this with your external webhook URL if needed
    "ALERT_WEBHOOK_URL": "http://127.0.0.1:8001/webhook", 
    "ALERT_INTERVAL": 5,
}

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
    count = 0
    async with httpx.AsyncClient() as client_http:
        while True:
            try:
                data = generate_ohlcv()
                count += 1

                # Every Nth data point: Send Alert/Signal
                if count % CONFIG["ALERT_INTERVAL"] == 0:
                    print(f"--- ALERT: Sending Signal to {CONFIG['ALERT_WEBHOOK_URL']} (Count: {count}) ---")
                    try:
                        await client_http.post(CONFIG["ALERT_WEBHOOK_URL"], json=data)
                    except Exception as e:
                        print(f"Alert Failed: {e}")

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
    print("DEBUG: Root (/) route hit")
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
# Webhook Endpoint (Alert Receiver)
# =========================
@app.get("/webhook")
async def webhook_status():
    """
    Status check for the webhook endpoint.
    """
    print("DEBUG: Webhook GET route hit")
    return {
        "status": "online",
        "message": "Webhook endpoint is active. Send a POST request to trigger an alert.",
        "alert_interval": CONFIG["ALERT_INTERVAL"],
        "target_url": CONFIG["ALERT_WEBHOOK_URL"]
    }

@app.post("/webhook")
async def alert_webhook(data: dict):
    """
    Simple endpoint to receive and log alerts/signals.
    """
    print(f"DEBUG: Webhook POST hit with data: {data.get('symbol')}")
    print(f"🔔 SIGNAL RECEIVED: {data.get('symbol')} at {data.get('close')}")
    return {"status": "alert_processed", "timestamp": datetime.now().isoformat()}

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