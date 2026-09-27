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