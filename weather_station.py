#!/usr/bin/env python3
import socket
import time
import random
import json
import sys

HOST = "127.0.0.1"
PORT = 39000

# -----------------------------
# Gaussian weather generator
# -----------------------------
def gaussian_weather(station_type="normal"):
    # Default climate profile
    climate = {
        "temp_mean": 18, "temp_std": 7,
        "hum_mean": 55, "hum_std": 20,
        "wind_mean": 8, "wind_std": 5
    }

    # Climate profiles per station type
    if station_type == "coastal":
        climate.update({
            "temp_mean": 20, "temp_std": 4,
            "hum_mean": 75, "hum_std": 10,
            "wind_mean": 12, "wind_std": 6
        })

    elif station_type == "mountain":
        climate.update({
            "temp_mean": 5, "temp_std": 8,
            "hum_mean": 40, "hum_std": 15,
            "wind_mean": 18, "wind_std": 10
        })

    elif station_type == "desert":
        climate.update({
            "temp_mean": 33, "temp_std": 7,
            "hum_mean": 20, "hum_std": 10,
            "wind_mean": 6, "wind_std": 4
        })

    # Generate Gaussian values
    temperature = round(random.gauss(climate["temp_mean"], climate["temp_std"]), 1)
    humidity = round(random.gauss(climate["hum_mean"], climate["hum_std"]), 1)
    wind = round(abs(random.gauss(climate["wind_mean"], climate["wind_std"])), 1)

    # Clamp to realistic limits
    temperature = max(-30, min(50, temperature))
    humidity = max(0, min(100, humidity))
    wind = max(0, min(120, wind))

    return temperature, humidity, wind


def extract_station_type(station_id):
    """
    Allows naming like:
      station01_coastal
      station02_desert
      mymountainstation_mountain
      sensorA_normal
    """
    parts = station_id.lower().split("_")
    if len(parts) > 1:
        return parts[-1]  # what comes after last underscore
    return "normal"


def main():
    # read station ID from command line
    if len(sys.argv) < 2:
        print("Usage: python client.py <station_id>")
        return

    station_id = sys.argv[1]
    station_type = extract_station_type(station_id)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    print(f"Connected to server as {station_id} (type={station_type})")

    try:
        while True:
            temperature, humidity, wind = gaussian_weather(station_type)

            message = {
                "station_id": station_id,
                "timestamp": time.time(),
                "temperature": temperature,
                "humidity": humidity,
                "wind": wind
            }

            msg_json = json.dumps(message) + "\n"
            print("Sending:", msg_json.strip())
            s.sendall(msg_json.encode())

            time.sleep(1.5)

    except KeyboardInterrupt:
        print("Client stopped.")

    finally:
        s.close()


if __name__ == "__main__":
    main()
