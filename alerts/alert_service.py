from datetime import datetime

from backend.models import Alert


def create_status_alert(
    db,
    device,
    previous_status,
    current_status
):

    # -----------------------------------
    # DEVICE DOWN
    # -----------------------------------

    if current_status == "offline":

        alert = Alert(
            device_id=device.id,
            device_name=device.name,
            ip_address=device.ip_address,
            event_type="DEVICE_DOWN",
            severity="CRITICAL",
            previous_status=previous_status,
            current_status=current_status,
            message=(
                f"{device.name} ({device.ip_address}) "
                f"is unreachable."
            ),
            incident_status="OPEN"
        )

        db.add(alert)

        return alert

    # -----------------------------------
    # DEVICE RECOVERED
    # -----------------------------------

    if (
        previous_status == "offline"
        and current_status == "online"
    ):

        # Find latest open DEVICE_DOWN incident
        open_incident = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.event_type == "DEVICE_DOWN",
                Alert.incident_status == "OPEN"
            )
            .order_by(Alert.created_at.desc())
            .first()
        )

        # Resolve original outage
        if open_incident:

            open_incident.incident_status = "RESOLVED"
            open_incident.resolved_at = datetime.utcnow()

        # Create recovery event
        recovery_alert = Alert(
            device_id=device.id,
            device_name=device.name,
            ip_address=device.ip_address,
            event_type="DEVICE_RECOVERED",
            severity="INFO",
            previous_status=previous_status,
            current_status=current_status,
            message=(
                f"{device.name} ({device.ip_address}) "
                f"has recovered and is reachable."
            ),
            incident_status="RESOLVED",
            resolved_at=datetime.utcnow()
        )

        db.add(recovery_alert)

        return recovery_alert

    return None

def create_performance_alert(
    db,
    device,
    event_type
):

    # -----------------------------------
    # PERFORMANCE DEGRADED
    # -----------------------------------

    if event_type == "PERFORMANCE_DEGRADED":

        # Prevent duplicate open performance incidents
        existing_incident = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.event_type == "PERFORMANCE_DEGRADED",
                Alert.incident_status == "OPEN"
            )
            .first()
        )

        if existing_incident:
            return None

        alert = Alert(
            device_id=device.id,
            device_name=device.name,
            ip_address=device.ip_address,
            event_type="PERFORMANCE_DEGRADED",
            severity="WARNING",
            previous_status="normal",
            current_status="high_latency",
            message=(
                f"{device.name} ({device.ip_address}) "
                f"is experiencing high latency: "
                f"{device.latency} ms."
            ),
            incident_status="OPEN"
        )

        db.add(alert)

        return alert

    # -----------------------------------
    # PERFORMANCE RECOVERED
    # -----------------------------------

    if event_type == "PERFORMANCE_RECOVERED":

        open_incident = (
            db.query(Alert)
            .filter(
                Alert.device_id == device.id,
                Alert.event_type == "PERFORMANCE_DEGRADED",
                Alert.incident_status == "OPEN"
            )
            .order_by(Alert.created_at.desc())
            .first()
        )

        # No open performance incident = nothing to recover
        if not open_incident:
            return None

        open_incident.incident_status = "RESOLVED"
        open_incident.resolved_at = datetime.utcnow()

        recovery_alert = Alert(
            device_id=device.id,
            device_name=device.name,
            ip_address=device.ip_address,
            event_type="PERFORMANCE_RECOVERED",
            severity="INFO",
            previous_status="high_latency",
            current_status="normal",
            message=(
                f"{device.name} ({device.ip_address}) "
                f"latency has returned to normal: "
                f"{device.latency} ms."
            ),
            incident_status="RESOLVED",
            resolved_at=datetime.utcnow()
        )

        db.add(recovery_alert)

        return recovery_alert

    return None