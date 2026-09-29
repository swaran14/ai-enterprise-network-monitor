import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from monitoring.monitor_service import monitor_all_devices
from monitoring.ping_monitor import ping_device
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from backend.schemas import DeviceCreate, DeviceResponse, DeviceUpdate

from backend.database import Base, engine, get_db
from backend.models import Device, Alert
from backend.schemas import DeviceCreate, DeviceResponse


def ensure_alert_schema():
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    if "alerts" not in table_names:
        Base.metadata.create_all(bind=engine)
        return

    existing_columns = {
        column["name"] for column in inspector.get_columns("alerts")
    }

    with engine.begin() as connection:
        if "incident_status" not in existing_columns:
            connection.execute(
                text(
                    "ALTER TABLE alerts ADD COLUMN incident_status VARCHAR DEFAULT 'OPEN'"
                )
            )

        if "resolved_at" not in existing_columns:
            connection.execute(
                text("ALTER TABLE alerts ADD COLUMN resolved_at DATETIME")
            )


Base.metadata.create_all(bind=engine)
ensure_alert_schema()

@asynccontextmanager
async def lifespan(app: FastAPI):

    print("[SYSTEM] Starting automatic network monitoring...")

    monitoring_task = asyncio.create_task(
        monitor_all_devices()
    )

    yield

    print("[SYSTEM] Stopping automatic network monitoring...")

    monitoring_task.cancel()

    try:
        await monitoring_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="AI-Driven Enterprise Network Monitoring & Automation Platform",
    description="Enterprise network monitoring, automation and AI-assisted troubleshooting.",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/")
def home():
    return {
        "project": "AI-Driven Enterprise Network Monitoring & Automation Platform",
        "status": "running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/devices", response_model=DeviceResponse)
def create_device(
    device: DeviceCreate,
    db: Session = Depends(get_db)
):
    existing = (
        db.query(Device)
        .filter(Device.ip_address == device.ip_address)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="A device with this IP address already exists"
        )

    new_device = Device(**device.model_dump())

    db.add(new_device)
    db.commit()
    db.refresh(new_device)

    return new_device


@app.get("/devices", response_model=list[DeviceResponse])
def get_devices(
    db: Session = Depends(get_db)
):
    return db.query(Device).all()


@app.get("/devices/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: int,
    db: Session = Depends(get_db)
):
    device = (
        db.query(Device)
        .filter(Device.id == device_id)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    return device


@app.delete("/devices/{device_id}")
def delete_device(
    device_id: int,
    db: Session = Depends(get_db)
):
    device = (
        db.query(Device)
        .filter(Device.id == device_id)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    db.delete(device)
    db.commit()

    return {
        "message": "Device deleted successfully"
    }


@app.post("/devices/{device_id}/monitor")
def monitor_device(
    device_id: int,
    db: Session = Depends(get_db)
):
    device = (
        db.query(Device)
        .filter(Device.id == device_id)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    result = ping_device(device.ip_address)

    device.status = result["status"]
    device.latency = result["latency"]

    if result["status"] == "online":
        device.last_seen = datetime.utcnow()

    db.commit()
    db.refresh(device)

    return {
        "id": device.id,
        "name": device.name,
        "ip_address": device.ip_address,
        "status": device.status,
        "latency": device.latency,
        "last_seen": device.last_seen
    }
@app.get("/alerts")
def get_alerts(
    db: Session = Depends(get_db)
):

    alerts = (
        db.query(Alert)
        .order_by(Alert.created_at.desc())
        .all()
    )

    return alerts

@app.patch("/devices/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    update: DeviceUpdate,
    db: Session = Depends(get_db)
):
    device = (
        db.query(Device)
        .filter(Device.id == device_id)
        .first()
    )

    if not device:
        raise HTTPException(
            status_code=404,
            detail="Device not found"
        )

    # Check whether another device already uses this IP
    existing_device = (
        db.query(Device)
        .filter(
            Device.ip_address == update.ip_address,
            Device.id != device_id
        )
        .first()
    )

    if existing_device:
        raise HTTPException(
            status_code=400,
            detail="A device with this IP address already exists"
        )

    device.ip_address = update.ip_address

    db.commit()
    db.refresh(device)

    return device