import asyncio
from pydantic import BaseModel
from automation.ssh_service import execute_ssh_command, ALLOWED_COMMANDS
from contextlib import asynccontextmanager
from datetime import datetime
from monitoring.monitor_service import monitor_all_devices
from monitoring.ping_monitor import ping_device
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import inspect, text, func
from sqlalchemy.orm import Session
from backend.schemas import (
    DeviceCreate,
    DeviceResponse,
    DeviceUpdate,
    DeviceSSHCommandRequest
)

from backend.database import Base, engine, get_db
from backend.models import (
    Device,
    Alert,
    PerformanceMetric,
    AutomationHistory
)


class SSHCommandRequest(BaseModel):
    host: str
    username: str
    password: str
    command: str
    port: int = 22



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
@app.get("/analytics/summary")
def get_analytics_summary(
    db: Session = Depends(get_db)
):
    # -----------------------------
    # DEVICE COUNTS
    # -----------------------------

    total_devices = db.query(Device).count()

    online_devices = (
        db.query(Device)
        .filter(Device.status == "online")
        .count()
    )

    offline_devices = (
        db.query(Device)
        .filter(Device.status == "offline")
        .count()
    )

    unknown_devices = (
        db.query(Device)
        .filter(Device.status == "unknown")
        .count()
    )

    # -----------------------------
    # INCIDENT COUNTS
    # -----------------------------

    open_incidents = (
        db.query(Alert)
        .filter(Alert.incident_status == "OPEN")
        .count()
    )

    critical_incidents = (
        db.query(Alert)
        .filter(
            Alert.incident_status == "OPEN",
            Alert.severity == "CRITICAL"
        )
        .count()
    )

    warning_incidents = (
        db.query(Alert)
        .filter(
            Alert.incident_status == "OPEN",
            Alert.severity == "WARNING"
        )
        .count()
    )

    # -----------------------------
    # CURRENT AVERAGE LATENCY
    # -----------------------------

    average_latency = (
        db.query(func.avg(Device.latency))
        .filter(
            Device.status == "online",
            Device.latency.isnot(None)
        )
        .scalar()
    )

    if average_latency is not None:
        average_latency = round(average_latency, 2)

    # -----------------------------
    # NETWORK HEALTH
    # -----------------------------

    if total_devices > 0:
        network_health_percentage = round(
            (online_devices / total_devices) * 100,
            2
        )
    else:
        network_health_percentage = 0.0

    return {
        "total_devices": total_devices,
        "online_devices": online_devices,
        "offline_devices": offline_devices,
        "unknown_devices": unknown_devices,
        "open_incidents": open_incidents,
        "critical_incidents": critical_incidents,
        "warning_incidents": warning_incidents,
        "average_latency_ms": average_latency,
        "network_health_percentage": network_health_percentage
    }
@app.get("/analytics/latency/{device_id}")
def get_device_latency_history(
    device_id: int,
    limit: int = 50,
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

    metrics = (
        db.query(PerformanceMetric)
        .filter(
            PerformanceMetric.device_id == device_id,
            PerformanceMetric.latency.isnot(None)
        )
        .order_by(PerformanceMetric.recorded_at.desc())
        .limit(limit)
        .all()
    )

    # Return oldest -> newest for frontend charts
    metrics.reverse()

    return {
        "device_id": device.id,
        "device_name": device.name,
        "ip_address": device.ip_address,
        "current_status": device.status,
        "current_latency_ms": device.latency,
        "data_points": len(metrics),
        "history": [
            {
                "latency_ms": metric.latency,
                "status": metric.status,
                "recorded_at": metric.recorded_at
            }
            for metric in metrics
        ]
    }


@app.get("/automation/ssh/commands")
def get_allowed_ssh_commands():
    return {
        "commands": sorted(ALLOWED_COMMANDS)
    }


@app.post("/automation/ssh/execute")
async def run_ssh_command(
    request: SSHCommandRequest,
    db: Session = Depends(get_db)
):
    result = await asyncio.to_thread(
        execute_ssh_command,
        request.host,
        request.username,
        request.password,
        request.command,
        request.port
    )

    history = AutomationHistory(
        host=request.host,
        username=request.username,
        command=request.command.strip().lower(),
        success=1 if result.get("success") else 0,
        error_type=result.get("error_type"),
        output=(
            result.get("output")
            or result.get("message")
            or result.get("error_output")
        )
    )
    db.add(history)
    db.commit()
    db.refresh(history)

    return result


@app.post("/automation/devices/{device_id}/execute")
async def run_device_ssh_command(
    device_id: int,
    request: DeviceSSHCommandRequest,
    db: Session = Depends(get_db)
):
    # Find device in database
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

    # Execute SSH command using device IP from database
    result = await asyncio.to_thread(
        execute_ssh_command,
        device.ip_address,
        request.username,
        request.password,
        request.command,
        request.port
    )

    # Store execution history
    history = AutomationHistory(
        host=device.ip_address,
        username=request.username,
        command=request.command.strip().lower(),
        success=1 if result.get("success") else 0,
        error_type=result.get("error_type"),
        output=(
            result.get("output")
            or result.get("message")
            or result.get("error_output")
        )
    )
    db.add(history)
    db.commit()

    return {
        "device": {
            "id": device.id,
            "name": device.name,
            "ip_address": device.ip_address
        },
        "result": result
    }


@app.get("/automation/history")
def get_automation_history(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    limit = max(1, min(limit, 200))
    history = (
        db.query(AutomationHistory)
        .order_by(AutomationHistory.executed_at.desc())
        .limit(limit)
        .all()
    )
    return history
@app.get("/analytics/devices")
def get_device_analytics(
    db: Session = Depends(get_db)
):
    devices = db.query(Device).all()

    results = []

    for device in devices:

        open_incidents = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.incident_status == "OPEN"
            )
            .count()
        )

        average_latency = (
            db.query(func.avg(PerformanceMetric.latency))
            .filter(
                PerformanceMetric.device_id == device.id,
                PerformanceMetric.latency.isnot(None)
            )
            .scalar()
        )

        if average_latency is not None:
            average_latency = round(average_latency, 2)

        total_metrics = (
            db.query(PerformanceMetric)
            .filter(
                PerformanceMetric.device_id == device.id
            )
            .count()
        )

        online_metrics = (
            db.query(PerformanceMetric)
            .filter(
                PerformanceMetric.device_id == device.id,
                PerformanceMetric.status == "online"
            )
            .count()
        )

        if total_metrics > 0:
            uptime_percentage = round(
                (online_metrics / total_metrics) * 100,
                2
            )
        else:
            uptime_percentage = 0.0

        results.append({
            "device_id": device.id,
            "name": device.name,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "location": device.location,
            "status": device.status,
            "current_latency_ms": device.latency,
            "average_latency_ms": average_latency,
            "uptime_percentage": uptime_percentage,
            "open_incidents": open_incidents,
            "last_seen": device.last_seen
        })

    return results

@app.get("/analytics/device/{device_id}")
def get_single_device_analytics(
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

    total_metrics = (
        db.query(PerformanceMetric)
        .filter(PerformanceMetric.device_id == device_id)
        .count()
    )

    online_metrics = (
        db.query(PerformanceMetric)
        .filter(
            PerformanceMetric.device_id == device_id,
            PerformanceMetric.status == "online"
        )
        .count()
    )

    average_latency = (
        db.query(func.avg(PerformanceMetric.latency))
        .filter(
            PerformanceMetric.device_id == device_id,
            PerformanceMetric.latency.isnot(None)
        )
        .scalar()
    )

    maximum_latency = (
        db.query(func.max(PerformanceMetric.latency))
        .filter(
            PerformanceMetric.device_id == device_id,
            PerformanceMetric.latency.isnot(None)
        )
        .scalar()
    )

    minimum_latency = (
        db.query(func.min(PerformanceMetric.latency))
        .filter(
            PerformanceMetric.device_id == device_id,
            PerformanceMetric.latency.isnot(None)
        )
        .scalar()
    )

    open_incidents = (
        db.query(Alert)
        .filter(
            Alert.device_id == device_id,
            Alert.incident_status == "OPEN"
        )
        .count()
    )

    total_alerts = (
        db.query(Alert)
        .filter(Alert.device_id == device_id)
        .count()
    )

    if total_metrics > 0:
        uptime_percentage = round(
            (online_metrics / total_metrics) * 100,
            2
        )
    else:
        uptime_percentage = 0.0

    if average_latency is not None:
        average_latency = round(average_latency, 2)

    return {
        "device": {
            "id": device.id,
            "name": device.name,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "location": device.location,
            "status": device.status,
            "last_seen": device.last_seen
        },

        "performance": {
            "current_latency_ms": device.latency,
            "average_latency_ms": average_latency,
            "minimum_latency_ms": minimum_latency,
            "maximum_latency_ms": maximum_latency,
            "uptime_percentage": uptime_percentage,
            "total_measurements": total_metrics
        },

        "incidents": {
            "open_incidents": open_incidents,
            "total_alerts": total_alerts
        }
    }

@app.get("/analytics/alerts")
def get_alert_analytics(
    db: Session = Depends(get_db)
):
    total_alerts = db.query(Alert).count()

    open_incidents = (
        db.query(Alert)
        .filter(Alert.incident_status == "OPEN")
        .count()
    )

    resolved_incidents = (
        db.query(Alert)
        .filter(Alert.incident_status == "RESOLVED")
        .count()
    )

    critical_alerts = (
        db.query(Alert)
        .filter(Alert.severity == "CRITICAL")
        .count()
    )

    warning_alerts = (
        db.query(Alert)
        .filter(Alert.severity == "WARNING")
        .count()
    )

    info_alerts = (
        db.query(Alert)
        .filter(Alert.severity == "INFO")
        .count()
    )

    device_down_events = (
        db.query(Alert)
        .filter(Alert.event_type == "DEVICE_DOWN")
        .count()
    )

    recovery_events = (
        db.query(Alert)
        .filter(Alert.event_type == "DEVICE_RECOVERED")
        .count()
    )

    performance_degraded_events = (
        db.query(Alert)
        .filter(Alert.event_type == "PERFORMANCE_DEGRADED")
        .count()
    )

    performance_recovered_events = (
        db.query(Alert)
        .filter(Alert.event_type == "PERFORMANCE_RECOVERED")
        .count()
    )

    recent_alerts = (
        db.query(Alert)
        .order_by(Alert.created_at.desc())
        .limit(10)
        .all()
    )

    return {
        "summary": {
            "total_alerts": total_alerts,
            "open_incidents": open_incidents,
            "resolved_incidents": resolved_incidents
        },

        "severity_breakdown": {
            "critical": critical_alerts,
            "warning": warning_alerts,
            "info": info_alerts
        },

        "event_breakdown": {
            "device_down": device_down_events,
            "device_recovered": recovery_events,
            "performance_degraded": performance_degraded_events,
            "performance_recovered": performance_recovered_events
        },

        "recent_alerts": [
            {
                "id": alert.id,
                "device_id": alert.device_id,
                "device_name": alert.device_name,
                "ip_address": alert.ip_address,
                "event_type": alert.event_type,
                "severity": alert.severity,
                "message": alert.message,
                "incident_status": alert.incident_status,
                "created_at": alert.created_at,
                "resolved_at": alert.resolved_at
            }
            for alert in recent_alerts
        ]
    }