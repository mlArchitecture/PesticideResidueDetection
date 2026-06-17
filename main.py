from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
from datetime import datetime
import json
import binascii
import qrcode
import io
import base64
from fastapi.responses import StreamingResponse
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

app = FastAPI()

# ─── DB SETUP ─────────────────────────────────────────────────────────────────

conn = sqlite3.connect("sensor.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS sensor_data_new (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    deviceId  TEXT    NOT NULL,
    pHvalue   REAL    NOT NULL,
    adcValue  REAL    NOT NULL,
    timestamp TEXT    NOT NULL
)
""")

conn.commit()

# ─── LOAD PUBLIC KEY ──────────────────────────────────────────────────────────

with open("./utils/public_key.pem", "rb") as f:
    PUBLIC_KEY = serialization.load_pem_public_key(f.read())

# ─── MODELS ───────────────────────────────────────────────────────────────────

class SensorPacket(BaseModel):
    data: str        # raw JSON string from ESP32
    signature: str   # hex-encoded DER signature


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Welcome to the Sensor Data API"}


@app.post("/sensor")
def receive_sensor_data(packet: SensorPacket):
    print("I am started!")
    # 1. Decode signature from hex
    try:
        sig_bytes = binascii.unhexlify(packet.signature)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid signature hex")

    # 2. Verify ECDSA signature over raw data string
    try:
        PUBLIC_KEY.verify(
            sig_bytes,
            packet.data.encode("utf-8"),
            ec.ECDSA(hashes.SHA256())
        )
    except InvalidSignature:
        raise HTTPException(status_code=401, detail="Invalid signature — data rejected")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Signature verification error: {str(e)}")

    # 3. Parse the inner data JSON string
    try:
        sensor = json.loads(packet.data)
        print("Received sensor data:")
        print(sensor)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in data field")

    # 4. Extract fields
    try:
        device_id = sensor["deviceId"]
        ph_value  = float(sensor["pHValue"])
        adc_value = float(sensor["adcValue"])
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing field: {e}")

    # 5. Store to DB
    timestamp = datetime.now().isoformat()

    cursor.execute(
        """
        INSERT INTO sensor_data_new (deviceId, pHvalue, adcValue, timestamp)
        VALUES (?, ?, ?, ?)
        """,
        (device_id, ph_value, adc_value, timestamp)
    )
    conn.commit()
    
    qr_data = json.dumps({
        "deviceId":  device_id,
        "pHValue":   ph_value,
        "adcValue":  adc_value,
        "timestamp": timestamp
    })

    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L)
    qr.add_data(qr_data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    img.save("qr_code.png",format="PNG")
    qrLink = f"https://pesticideresiduedetection-1.onrender.com/qr-code/{device_id}/{timestamp}"

    return {
        "message": "Data verified and stored successfully",
        "deviceId": device_id,
        "pHValue": ph_value,
        "adcValue": adc_value,
        "timestamp": timestamp,
        "qrCodeLink": qrLink
    }



@app.get("/qr-code/{device_id}/{timestamp}")
def get_qr(device_id: str, timestamp: str):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    cursor.execute("SELECT * FROM sensor_data_new WHERE deviceId = ? AND timestamp = ?", (device_id, timestamp))
    row = cursor.fetchone()
    qr_json = json.dumps({
        "deviceId": row[1],
        "pHValue": row[2],
        "adcValue": row[3],
        "timestamp": row[4]
    }) if row else json.dumps({'deviceId': 'test', 'pHValue': 6.8})

    return qr_json


@app.get("/sensor")
def get_sensor_data():

    cursor.execute("""
        SELECT * FROM sensor_data_new
        ORDER BY id DESC
        LIMIT 100
    """)

    rows = cursor.fetchall()

    return [
        {
            "id":        row[0],
            "deviceId":  row[1],
            "pHValue":   row[2],
            "adcValue":  row[3],
            "timestamp": row[4]
        }
        for row in rows
    ]