from pydantic import BaseModel, ConfigDict
from datetime import datetime


class DeviceCreate(BaseModel):
    name: str
    ip_address: str
    device_type: str
    location: str | None = None


class DeviceResponse(DeviceCreate):
    id: int
    status: str
    latency: float | None = None
    last_seen: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DeviceUpdate(BaseModel):
    ip_address: str
class DeviceSSHCommandRequest(BaseModel):
    username: str
    password: str
    command: str
    port: int = 22

class RemediationDecisionRequest(BaseModel):
    decision_by: str
    decision_note: str | None = None