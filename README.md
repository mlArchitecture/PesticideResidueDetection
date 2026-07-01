# Pesticide Residue Detection System — Backend

A secure, IoT-based backend service for collecting and verifying pesticide residue sensor data from an ESP32-based field device. The backend authenticates incoming sensor readings using ECDSA digital signatures, persists them to a database, and generates QR codes for quick result verification and traceability.

## 🌱 Overview

This backend powers a pesticide detection system where an ESP32 microcontroller reads pH/ADC values from a sensor node, cryptographically signs the data, and transmits it over HTTP to this FastAPI service. The server verifies the signature to ensure data integrity and authenticity before storing it, then generates a scannable QR code that links directly to the verified reading — allowing anyone in the field to instantly confirm results.

## ✨ Features

- **Cryptographically Verified Data Ingestion** — Every sensor payload is signed on-device using ECDSA (SHA-256) and verified server-side before being trusted or stored, preventing data tampering or spoofing.
- **Persistent Storage** — Sensor readings (device ID, pH value, ADC value, timestamp) are stored in a lightweight SQLite database.
- **QR Code Generation** — Each verified reading is encoded into a QR code, enabling quick, tamper-evident result sharing and field verification.
- **RESTful API** — Simple endpoints to submit sensor data, retrieve QR codes, and fetch recent readings.

## 🏗️ Architecture

```
ESP32 Sensor Node (pH sensor + ECDSA signing via mbedTLS)
        │
        │  HTTP POST (signed JSON payload)
        ▼
FastAPI Backend
        │
        ├── Verifies ECDSA signature (public key)
        ├── Parses & validates sensor payload
        ├── Persists to SQLite (sensor_data_new)
        └── Generates QR code for the reading
        ▼
TFT Display / QR Scan for Field Verification
```

## 🛠️ Tech Stack

| Layer              | Technology                          |
|--------------------|--------------------------------------|
| API Framework      | FastAPI                              |
| Database           | SQLite                               |
| Cryptography       | `cryptography` (ECDSA, SHA-256)      |
| QR Code Generation | `qrcode`                             |
| Data Validation    | Pydantic                             |
| Device Firmware    | ESP32 (mbedTLS 3.x for signing)      |

## 📡 API Endpoints

### `GET /`
Health check endpoint.

**Response:**
```json
{ "message": "Welcome to the Sensor Data API" }
```

---

### `POST /sensor`
Receives a signed sensor data packet from the ESP32 device, verifies its authenticity, and stores it.

**Request Body:**
```json
{
  "data": "{\"deviceId\":\"esp32-01\",\"pHValue\":6.8,\"adcValue\":2048}",
  "signature": "<hex-encoded DER ECDSA signature>"
}
```

**Response:**
```json
{
  "message": "Data verified and stored successfully",
  "deviceId": "esp32-01",
  "pHValue": 6.8,
  "adcValue": 2048,
  "timestamp": "2026-07-01T12:00:00",
  "qrCodeLink": "https://.../qr-code/esp32-01/2026-07-01T12:00:00"
}
```

**Errors:**
| Status | Reason                                  |
|--------|------------------------------------------|
| 400    | Malformed signature hex or invalid JSON   |
| 401    | Signature verification failed             |

---

### `GET /qr-code/{device_id}/{timestamp}`
Fetches the stored reading corresponding to a given device and timestamp, as encoded in a scanned QR code.

**Response:**
```json
{
  "deviceId": "esp32-01",
  "pHValue": 6.8,
  "adcValue": 2048,
  "timestamp": "2026-07-01T12:00:00"
}
```

---

### `GET /sensor`
Returns the 100 most recent sensor readings, ordered by newest first.

**Response:**
```json
[
  {
    "id": 1,
    "deviceId": "esp32-01",
    "pHValue": 6.8,
    "adcValue": 2048,
    "timestamp": "2026-07-01T12:00:00"
  }
]
```

## 🔐 Security Model

Each ESP32 device signs its outgoing data using an ECDSA private key (SHA-256 digest) on-device. The backend loads the corresponding public key at startup (`./utils/public_key.pem`) and verifies every incoming payload before accepting it into the database. This ensures:

- **Authenticity** — Only devices holding the correct private key can submit valid data.
- **Integrity** — Any tampering with the payload in transit invalidates the signature.

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- An ECDSA key pair (`public_key.pem` for the server, matching private key on the ESP32 device)

### Installation

```bash
pip install fastapi uvicorn cryptography qrcode[pil] python-multipart
```

### Running the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Project Structure

```
backend/
├── main.py
├── sensor.db              # Auto-created SQLite database
├── utils/
│   └── public_key.pem      # ECDSA public key for signature verification
└── qr_code.png              # Most recently generated QR code (debug output)
```

## 📌 Notes

- The database table `sensor_data_new` is created automatically on startup if it doesn't already exist.
- QR codes are generated using error correction level `L` on ingestion and `H` on retrieval for improved scan reliability.
- Timestamps are stored in ISO 8601 format using server local time.

## 🗺️ Future Improvements

- Migrate from SQLite to PostgreSQL for concurrent write support at scale
- Add device registration/whitelisting so only known device IDs are accepted
- Add pesticide concentration classification logic based on pH/ADC readings
- Containerize with Docker for consistent deployment
