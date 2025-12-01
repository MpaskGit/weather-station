#!/usr/bin/env python3
import asyncio
import json
import logging
import re
import sqlite3
from pathlib import Path
from aiohttp import web

HOST = "127.0.0.1"
PORT = 39000
DB_PATH = Path("weather.db")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
)

SAFE_NAME = re.compile(r"^[a-zA-Z0-9_\-]+$")

def sanitize(name: str) -> str:
    if not SAFE_NAME.match(name):
        raise ValueError(f"Unsafe station_id: {name!r}")
    return name


# --------------------------------------------------------
# 🔥 NEW: Extract station location from station_id
# --------------------------------------------------------
def extract_station_location(station_id: str) -> str:
    """
    Examples:
      station01_coastal   -> coastal
      station02_mountain  -> mountain
      station03_desert    -> desert
      station04           -> station04 (fallback)
    """
    parts = station_id.split("_")
    if len(parts) > 1:
        return parts[-1]  # location part
    return station_id     # fallback if no location provided


def get_latest_data(limit=40):
    conn = sqlite3.connect("weather.db")
    cur = conn.cursor()

    cur.execute("""
        SELECT station_id, timestamp, temperature, humidity, wind
        FROM weather_data
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cur.fetchall()
    conn.close()

    return rows


async def handle_web(request):
    rows = get_latest_data()

    html = """
    <html>
    <head>
        <title>Weather Station Monitor</title>
        <meta http-equiv="refresh" content="2">
        <style>
            body { font-family: Arial; padding: 20px; }
            table { border-collapse: collapse; width: 100%; }
            th, td { border: 1px solid #ccc; padding: 8px; }
            th { background: #eee; }
        </style>
    </head>
    <body>
        <h2>Weather Station Live Data</h2>
        <p>(Auto-refreshes every 2 seconds)</p>
        <table>
            <tr>
                <th>Location</th>
                <th>Timestamp</th>
                <th>Temp</th>
                <th>Humidity</th>
                <th>Wind</th>
            </tr>
    """

    for s, ts, t, h, w in rows:
        # 🔥 REPLACED: station_id -> location
        location = extract_station_location(s)
        html += f"<tr><td>{location}</td><td>{ts:.2f}</td><td>{t}</td><td>{h}</td><td>{w}</td></tr>"

    html += "</table></body></html>"

    return web.Response(text=html, content_type="text/html")

# -----------------------------
# Database setup
# -----------------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn

def init_database():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            station_id TEXT,
            timestamp REAL,
            temperature REAL,
            humidity REAL,
            wind REAL
        )
    """)
    conn.commit()
    conn.close()

def save_station_data(data: dict):
    station = sanitize(data["station_id"])
    table = f"{station}_data"

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO weather_data (station_id, timestamp, temperature, humidity, wind)
        VALUES (?, ?, ?, ?, ?)
    """, (
        data["station_id"],
        data["timestamp"],
        data["temperature"],
        data["humidity"],
        data["wind"]
    ))

    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS {table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            temperature REAL,
            humidity REAL,
            wind REAL
        )
    """)

    cur.execute(
        f"INSERT INTO {table} (timestamp, temperature, humidity, wind) VALUES (?, ?, ?, ?)",
        (data["timestamp"], data["temperature"], data["wind"], data["humidity"])
    )

    conn.commit()
    conn.close()

# -----------------------------
# Message handling
# -----------------------------
async def process_message(message: str):
    try:
        data = json.loads(message)
    except json.JSONDecodeError:
        logging.warning(f"Invalid JSON discarded: {message!r}")
        return

    required = {"station_id", "timestamp", "temperature", "humidity", "wind"}

    if not required.issubset(data):
        logging.warning(f"Missing required keys: {message!r}")
        return

    try:
        save_station_data(data)
        logging.info(f"Saved station={data['station_id']} temp={data['temperature']}")
    except Exception as e:
        logging.error(f"Database save error: {e}")

# -----------------------------
# Per-client handler
# -----------------------------
async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):

    addr = writer.get_extra_info("peername")
    logging.info(f"Client connected: {addr}")

    try:
        while True:
            try:
                data = await asyncio.wait_for(reader.readline(), timeout=60)
            except asyncio.TimeoutError:
                logging.warning(f"Client timed out: {addr}")
                break

            if not data:
                break

            message = data.decode("utf-8", errors="replace").strip()

            if len(message) > 2048:
                logging.warning(f"Dropped oversized message from {addr}")
                continue

            await process_message(message)

    except Exception as e:
        logging.error(f"Client error {addr}: {e}")

    finally:
        logging.info(f"Client disconnected: {addr}")
        writer.close()
        await writer.wait_closed()

# -----------------------------
# Main server
# -----------------------------
async def main():
    init_database()

    sensor_server = await asyncio.start_server(handle_client, HOST, PORT)
    print(f"Sensor server listening on {HOST}:{PORT}")

    app = web.Application()
    app.router.add_get("/", handle_web)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", 8080)
    await site.start()
    print("Web dashboard running at http://127.0.0.1:8080")

    async with sensor_server:
        await asyncio.gather(sensor_server.serve_forever())


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Server stopped.")
