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