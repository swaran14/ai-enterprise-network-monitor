import asyncio
from automation.config_compare import compare_configurations
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
    DeviceSSHCommandRequest,
    RemediationDecisionRequest
)
from backend.models import (
    Device,
    Alert,
    PerformanceMetric,
    AutomationHistory,
    ConfigurationBackup,
    ConfigurationChange,
    RemediationRequest
)

from backend.database import Base, engine, get_db
from backend.models import (
    Device,
    Alert,
    PerformanceMetric,
    AutomationHistory
)
from ai.diagnostic_engine import diagnose_device
from ai.health_score import calculate_health_score
from ai.root_cause import analyze_root_cause
from ai.remediation_engine import recommend_remediation

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

@app.post("/automation/devices/{device_id}/compare-config")
def compare_device_configuration(
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

    # Only successful backups contain usable configurations.
    backups = (
        db.query(ConfigurationBackup)
        .filter(
            ConfigurationBackup.device_id == device_id,
            ConfigurationBackup.backup_status == "SUCCESS"
        )
        .order_by(ConfigurationBackup.created_at.desc())
        .limit(2)
        .all()
    )

    if len(backups) < 2:
        raise HTTPException(
            status_code=400,
            detail=(
                "At least two successful configuration "
                "backups are required for comparison"
            )
        )

    # Query is newest first.
    new_backup = backups[0]
    old_backup = backups[1]

    comparison = compare_configurations(
        old_backup.configuration,
        new_backup.configuration
    )

    change = ConfigurationChange(
        device_id=device.id,
        device_name=device.name,
        ip_address=device.ip_address,
        old_backup_id=old_backup.id,
        new_backup_id=new_backup.id,
        change_detected=(
            1 if comparison["change_detected"] else 0
        ),
        change_summary=comparison["summary"]
    )

    db.add(change)
    db.commit()
    db.refresh(change)

    return {
        "comparison_id": change.id,
        "device_id": device.id,
        "device_name": device.name,
        "ip_address": device.ip_address,
        "old_backup_id": old_backup.id,
        "new_backup_id": new_backup.id,
        "change_detected": comparison["change_detected"],
        "summary": comparison["summary"],
        "added_lines": comparison["added_lines"],
        "removed_lines": comparison["removed_lines"],
        "diff": comparison["diff"],
        "detected_at": change.detected_at
    }

@app.get("/automation/config-changes")
def get_configuration_changes(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    limit = max(1, min(limit, 200))

    changes = (
        db.query(ConfigurationChange)
        .order_by(ConfigurationChange.detected_at.desc())
        .limit(limit)
        .all()
    )

    return changes


@app.get("/automation/devices/{device_id}/config-changes")
def get_device_configuration_changes(
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

    limit = max(1, min(limit, 200))

    changes = (
        db.query(ConfigurationChange)
        .filter(ConfigurationChange.device_id == device_id)
        .order_by(ConfigurationChange.detected_at.desc())
        .limit(limit)
        .all()
    )

    return changes
 
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


@app.post("/automation/devices/{device_id}/backup")
async def backup_device_configuration(
    device_id: int,
    username: str,
    password: str,
    port: int = 22,
    db: Session = Depends(get_db)
):
    # Find device
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

    command = "show running-config"

    # Execute configuration backup command
    result = await asyncio.to_thread(
        execute_ssh_command,
        device.ip_address,
        username,
        password,
        command,
        port
    )

    # Successful backup
    if result.get("success"):
        backup = ConfigurationBackup(
            device_id=device.id,
            device_name=device.name,
            ip_address=device.ip_address,
            configuration=result.get("output"),
            backup_status="SUCCESS",
            error_message=None
        )

    # Failed backup
    else:
        backup = ConfigurationBackup(
            device_id=device.id,
            device_name=device.name,
            ip_address=device.ip_address,
            configuration=None,
            backup_status="FAILED",
            error_message=(
                result.get("message")
                or result.get("error_output")
                or "Unknown backup error"
            )
        )

    db.add(backup)

    # Also keep automation audit history
    history = AutomationHistory(
        host=device.ip_address,
        username=username,
        command=command,
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
    db.refresh(backup)

    return {
        "backup_id": backup.id,
        "device_id": device.id,
        "device_name": device.name,
        "ip_address": device.ip_address,
        "backup_status": backup.backup_status,
        "error_message": backup.error_message,
        "created_at": backup.created_at
    }


@app.get("/automation/backups")
def get_configuration_backups(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    limit = max(1, min(limit, 200))

    backups = (
        db.query(ConfigurationBackup)
        .order_by(ConfigurationBackup.created_at.desc())
        .limit(limit)
        .all()
    )

    return backups


@app.get("/automation/devices/{device_id}/backups")
def get_device_configuration_backups(
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

    limit = max(1, min(limit, 200))

    backups = (
        db.query(ConfigurationBackup)
        .filter(ConfigurationBackup.device_id == device_id)
        .order_by(ConfigurationBackup.created_at.desc())
        .limit(limit)
        .all()
    )

    return backups


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

@app.get("/ai/diagnose/{device_id}")
def diagnose_network_device(
    device_id: int,
    db: Session = Depends(get_db)
):
    # -----------------------------------
    # FIND DEVICE
    # -----------------------------------

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

    # -----------------------------------
    # OPEN INCIDENTS
    # -----------------------------------

    open_incidents = (
        db.query(Alert)
        .filter(
            Alert.device_id == device_id,
            Alert.incident_status == "OPEN"
        )
        .count()
    )

    # -----------------------------------
    # OPEN CRITICAL ALERTS
    # -----------------------------------

    critical_alerts = (
        db.query(Alert)
        .filter(
            Alert.device_id == device_id,
            Alert.incident_status == "OPEN",
            Alert.severity == "CRITICAL"
        )
        .count()
    )

    # -----------------------------------
    # OPEN WARNING ALERTS
    # -----------------------------------

    warning_alerts = (
        db.query(Alert)
        .filter(
            Alert.device_id == device_id,
            Alert.incident_status == "OPEN",
            Alert.severity == "WARNING"
        )
        .count()
    )

    # -----------------------------------
    # LATEST CONFIGURATION CHANGE
    # -----------------------------------

    latest_change = (
        db.query(ConfigurationChange)
        .filter(
            ConfigurationChange.device_id == device_id
        )
        .order_by(
            ConfigurationChange.detected_at.desc()
        )
        .first()
    )

    configuration_changed = bool(
        latest_change
        and latest_change.change_detected == 1
    )

    # -----------------------------------
    # DIAGNOSTIC ENGINE
    # -----------------------------------

    diagnosis = diagnose_device(
        status=device.status,
        latency=device.latency,
        open_incidents=open_incidents,
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        configuration_changed=configuration_changed
    )

    # -----------------------------------
    # HEALTH SCORE
    # -----------------------------------

    health_score = calculate_health_score(
        status=device.status,
        latency=device.latency,
        open_incidents=open_incidents,
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        configuration_changed=configuration_changed
    )

    root_cause = analyze_root_cause(
        status=device.status,
        latency=device.latency,
        open_incidents=open_incidents,
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        configuration_changed=configuration_changed
    )
    
    remediation = recommend_remediation(
        status=device.status,
        latency=device.latency,
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        configuration_changed=configuration_changed
    )

    return {

        "device": {
            "id": device.id,
            "name": device.name,
            "ip_address": device.ip_address,
            "device_type": device.device_type,
            "status": device.status,
            "latency_ms": device.latency,
            "last_seen": device.last_seen
        },

        "health": health_score,

        "evidence": {
            "open_incidents": open_incidents,
            "critical_alerts": critical_alerts,
            "warning_alerts": warning_alerts,
            "configuration_changed": configuration_changed,
            "latest_configuration_change": (
                latest_change.change_summary
                if latest_change
                else None
            )
        },

        "diagnosis": diagnosis,

        "root_cause_analysis": root_cause,

        "remediation": remediation
    }
@app.get("/ai/network-health")
def get_network_health(
    db: Session = Depends(get_db)
):
    devices = db.query(Device).all()

    device_results = []
    total_score = 0

    for device in devices:

        open_incidents = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.incident_status == "OPEN"
            )
            .count()
        )

        critical_alerts = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.incident_status == "OPEN",
                Alert.severity == "CRITICAL"
            )
            .count()
        )

        warning_alerts = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.incident_status == "OPEN",
                Alert.severity == "WARNING"
            )
            .count()
        )

        latest_change = (
            db.query(ConfigurationChange)
            .filter(
                ConfigurationChange.device_id == device.id
            )
            .order_by(
                ConfigurationChange.detected_at.desc()
            )
            .first()
        )

        configuration_changed = bool(
            latest_change
            and latest_change.change_detected == 1
        )

        health = calculate_health_score(
            status=device.status,
            latency=device.latency,
            open_incidents=open_incidents,
            critical_alerts=critical_alerts,
            warning_alerts=warning_alerts,
            configuration_changed=configuration_changed
        )

        total_score += health["score"]

        device_results.append({
            "device_id": device.id,
            "device_name": device.name,
            "ip_address": device.ip_address,
            "status": device.status,
            "latency_ms": device.latency,
            "health_score": health["score"],
            "health": health["health"]
        })

    if devices:
        overall_score = round(
            total_score / len(devices),
            2
        )
    else:
        overall_score = 0

    if overall_score >= 90:
        overall_health = "EXCELLENT"
    elif overall_score >= 75:
        overall_health = "GOOD"
    elif overall_score >= 50:
        overall_health = "DEGRADED"
    elif overall_score >= 25:
        overall_health = "POOR"
    else:
        overall_health = "CRITICAL"

    return {
        "overall_network_score": overall_score,
        "overall_network_health": overall_health,
        "total_devices": len(devices),
        "devices": device_results
    }


@app.post("/ai/remediation/{device_id}/request")
def create_remediation_request(
    device_id: int,
    db: Session = Depends(get_db)
):
    # -----------------------------------
    # FIND DEVICE
    # -----------------------------------

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

    # -----------------------------------
    # CURRENT ALERT EVIDENCE
    # -----------------------------------

    critical_alerts = (
        db.query(Alert)
        .filter(
            Alert.device_id == device_id,
            Alert.incident_status == "OPEN",
            Alert.severity == "CRITICAL"
        )
        .count()
    )

    warning_alerts = (
        db.query(Alert)
        .filter(
            Alert.device_id == device_id,
            Alert.incident_status == "OPEN",
            Alert.severity == "WARNING"
        )
        .count()
    )

    # -----------------------------------
    # LATEST CONFIGURATION CHANGE
    # -----------------------------------

    latest_change = (
        db.query(ConfigurationChange)
        .filter(
            ConfigurationChange.device_id == device_id
        )
        .order_by(
            ConfigurationChange.detected_at.desc()
        )
        .first()
    )

    configuration_changed = bool(
        latest_change
        and latest_change.change_detected == 1
    )

    # -----------------------------------
    # GENERATE REMEDIATION
    # -----------------------------------

    remediation = recommend_remediation(
        status=device.status,
        latency=device.latency,
        critical_alerts=critical_alerts,
        warning_alerts=warning_alerts,
        configuration_changed=configuration_changed
    )

    # Healthy device -> no request required
    if remediation["action"] == "NONE":
        raise HTTPException(
            status_code=400,
            detail="No remediation is currently required for this device"
        )

    # -----------------------------------
    # PREVENT DUPLICATE PENDING REQUEST
    # -----------------------------------

    existing_request = (
        db.query(RemediationRequest)
        .filter(
            RemediationRequest.device_id == device_id,
            RemediationRequest.action == remediation["action"],
            RemediationRequest.status == "PENDING"
        )
        .first()
    )

    if existing_request:
        raise HTTPException(
            status_code=400,
            detail=(
                f"A pending remediation request already exists "
                f"for this action. Request ID: {existing_request.id}"
            )
        )

    # -----------------------------------
    # CREATE REQUEST
    # -----------------------------------

    request_record = RemediationRequest(
        device_id=device.id,
        device_name=device.name,
        ip_address=device.ip_address,

        action=remediation["action"],
        title=remediation["title"],
        reason=remediation["reason"],

        risk=remediation["risk"],

        requires_approval=(
            1 if remediation["requires_approval"] else 0
        ),

        status="PENDING"
    )

    db.add(request_record)
    db.commit()
    db.refresh(request_record)

    return {
        "request_id": request_record.id,

        "device": {
            "id": device.id,
            "name": device.name,
            "ip_address": device.ip_address
        },

        "action": request_record.action,
        "title": request_record.title,
        "reason": request_record.reason,
        "risk": request_record.risk,

        "requires_approval": bool(
            request_record.requires_approval
        ),

        "status": request_record.status,
        "requested_at": request_record.requested_at,

        "suggested_commands": remediation[
            "suggested_commands"
        ]
    }

@app.get("/ai/remediation/requests")
def get_remediation_requests(
    status: str | None = None,
    db: Session = Depends(get_db)
):
    query = db.query(RemediationRequest)

    if status:
        query = query.filter(
            RemediationRequest.status == status.upper()
        )

    requests = (
        query
        .order_by(RemediationRequest.requested_at.desc())
        .all()
    )

    return requests

@app.post("/ai/remediation/requests/{request_id}/approve")
def approve_remediation_request(
    request_id: int,
    decision: RemediationDecisionRequest,
    db: Session = Depends(get_db)
):
    request_record = (
        db.query(RemediationRequest)
        .filter(RemediationRequest.id == request_id)
        .first()
    )

    if not request_record:
        raise HTTPException(
            status_code=404,
            detail="Remediation request not found"
        )

    if request_record.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Request cannot be approved because "
                f"its current status is {request_record.status}"
            )
        )

    request_record.status = "APPROVED"
    request_record.decided_at = datetime.utcnow()
    request_record.decision_by = decision.decision_by
    request_record.decision_note = decision.decision_note

    db.commit()
    db.refresh(request_record)

    return {
        "request_id": request_record.id,
        "device_id": request_record.device_id,
        "device_name": request_record.device_name,
        "action": request_record.action,
        "risk": request_record.risk,
        "status": request_record.status,
        "decision_by": request_record.decision_by,
        "decision_note": request_record.decision_note,
        "decided_at": request_record.decided_at,
        "execution_status": request_record.execution_status,
        "message": (
            "Remediation request approved. "
            "No configuration change has been executed yet."
        )
    }

@app.post("/ai/remediation/requests/{request_id}/reject")
def reject_remediation_request(
    request_id: int,
    decision: RemediationDecisionRequest,
    db: Session = Depends(get_db)
):
    request_record = (
        db.query(RemediationRequest)
        .filter(RemediationRequest.id == request_id)
        .first()
    )

    if not request_record:
        raise HTTPException(
            status_code=404,
            detail="Remediation request not found"
        )

    if request_record.status != "PENDING":
        raise HTTPException(
            status_code=400,
            detail=(
                f"Request cannot be rejected because "
                f"its current status is {request_record.status}"
            )
        )

    request_record.status = "REJECTED"
    request_record.decided_at = datetime.utcnow()
    request_record.decision_by = decision.decision_by
    request_record.decision_note = decision.decision_note

    db.commit()
    db.refresh(request_record)

    return {
        "request_id": request_record.id,
        "device_id": request_record.device_id,
        "device_name": request_record.device_name,
        "action": request_record.action,
        "risk": request_record.risk,
        "status": request_record.status,
        "decision_by": request_record.decision_by,
        "decision_note": request_record.decision_note,
        "decided_at": request_record.decided_at,
        "message": "Remediation request rejected."
    }