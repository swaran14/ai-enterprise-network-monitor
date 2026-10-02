from sqlalchemy import Column, Integer, String, Float, DateTime
from datetime import datetime

from backend.database import Base


class Device(Base):
    __tablename__ = "devices"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String, nullable=False)

    ip_address = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    device_type = Column(String, nullable=False)

    location = Column(String, nullable=True)

    status = Column(
        String,
        default="unknown"
    )

    latency = Column(
        Float,
        nullable=True
    )

    last_seen = Column(
        DateTime,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )
class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, nullable=False)

    device_name = Column(String, nullable=False)

    ip_address = Column(String, nullable=False)

    event_type = Column(String, nullable=False)

    severity = Column(String, nullable=False)

    previous_status = Column(String, nullable=True)

    current_status = Column(String, nullable=False)

    message = Column(String, nullable=False)

    incident_status = Column(
        String,
        default="OPEN"
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    resolved_at = Column(
        DateTime,
        nullable=True
    )
class PerformanceMetric(Base):
    __tablename__ = "performance_metrics"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    device_name = Column(
        String,
        nullable=False
    )

    ip_address = Column(
        String,
        nullable=False
    )

    status = Column(
        String,
        nullable=False
    )

    latency = Column(
        Float,
        nullable=True
    )

    recorded_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )


class AutomationHistory(Base):
    __tablename__ = "automation_history"

    id = Column(Integer, primary_key=True, index=True)
    host = Column(String, nullable=False, index=True)
    username = Column(String, nullable=False)
    command = Column(String, nullable=False)
    success = Column(Integer, nullable=False)
    error_type = Column(String, nullable=True)
    output = Column(String, nullable=True)
    executed_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

class ConfigurationBackup(Base):
    __tablename__ = "configuration_backups"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    device_name = Column(
        String,
        nullable=False
    )

    ip_address = Column(
        String,
        nullable=False
    )

    configuration = Column(
        String,
        nullable=True
    )

    backup_status = Column(
        String,
        nullable=False
    )

    error_message = Column(
        String,
        nullable=True
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        index=True
    )

class ConfigurationChange(Base):
    __tablename__ = "configuration_changes"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    device_name = Column(
        String,
        nullable=False
    )

    ip_address = Column(
        String,
        nullable=False
    )

    old_backup_id = Column(
        Integer,
        nullable=False
    )

    new_backup_id = Column(
        Integer,
        nullable=False
    )

    change_detected = Column(
        Integer,
        default=0,
        nullable=False
    )

    change_summary = Column(
        String,
        nullable=True
    )

    detected_at = Column(
        DateTime,
        default=datetime.utcnow
    )


class RemediationRequest(Base):
    __tablename__ = "remediation_requests"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, nullable=False, index=True)
    device_name = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)

    action = Column(String, nullable=False)
    title = Column(String, nullable=False)
    reason = Column(String, nullable=False)

    risk = Column(String, nullable=False)
    requires_approval = Column(Integer, default=1, nullable=False)

    status = Column(String, default="PENDING", nullable=False)

    requested_at = Column(DateTime, default=datetime.utcnow)

    decided_at = Column(DateTime, nullable=True)
    decision_by = Column(String, nullable=True)
    decision_note = Column(String, nullable=True)

    executed_at = Column(DateTime, nullable=True)
    execution_status = Column(String, nullable=True)

class TroubleshootingSession(Base):
    __tablename__ = "troubleshooting_sessions"

    id = Column(Integer, primary_key=True, index=True)

    remediation_request_id = Column(Integer, nullable=False, index=True)

    device_id = Column(Integer, nullable=False, index=True)
    device_name = Column(String, nullable=False)
    ip_address = Column(String, nullable=False)

    action = Column(String, nullable=False)

    status = Column(
        String,
        default="ACTIVE",
        nullable=False
    )

    current_step = Column(
        Integer,
        default=1,
        nullable=False
    )

    total_steps = Column(
        Integer,
        nullable=False
    )

    started_at = Column(
        DateTime,
        default=datetime.utcnow
    )

    completed_at = Column(
        DateTime,
        nullable=True
    )

    final_result = Column(
        String,
        nullable=True
    )


class TroubleshootingStep(Base):
    __tablename__ = "troubleshooting_steps"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        nullable=False,
        index=True
    )

    step_number = Column(
        Integer,
        nullable=False
    )

    title = Column(
        String,
        nullable=False
    )

    step_type = Column(
        String,
        nullable=False
    )

    instruction = Column(
        String,
        nullable=False
    )

    command = Column(
        String,
        nullable=True
    )

    status = Column(
        String,
        default="PENDING",
        nullable=False
    )

    result = Column(
        String,
        nullable=True
    )

    completed_at = Column(
        DateTime,
        nullable=True
    )