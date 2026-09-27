import asyncio
from datetime import datetime

from backend.database import SessionLocal
from backend.models import Device
from monitoring.ping_monitor import ping_device
from alerts.alert_service import create_status_alert


MONITOR_INTERVAL = 15

# Number of consecutive failures required
# before declaring a device offline.
FAILURE_THRESHOLD = 3

# Stores consecutive failures:
# {device_id: failure_count}
failure_counts = {}


async def monitor_all_devices():

    while True:

        db = SessionLocal()

        try:

            devices = db.query(Device).all()

            print(
                f"[MONITOR] Checking {len(devices)} device(s)..."
            )

            for device in devices:

                old_status = device.status

                result = await asyncio.to_thread(
                    ping_device,
                    device.ip_address
                )

                ping_status = result["status"]

                # ---------------------------------
                # DEVICE RESPONDED
                # ---------------------------------

                if ping_status == "online":

                    failure_counts[device.id] = 0

                    device.status = "online"
                    device.latency = result["latency"]
                    device.last_seen = datetime.utcnow()

                    print(
                        f"[DEVICE] {device.name} "
                        f"({device.ip_address}) "
                        f"-> ONLINE "
                        f"| Latency: {result['latency']}"
                    )

                # ---------------------------------
                # DEVICE FAILED TO RESPOND
                # ---------------------------------

                else:

                    current_count = failure_counts.get(device.id, 0)

                    if current_count < FAILURE_THRESHOLD:
                        current_count += 1

                    failure_counts[device.id] = current_count
                    failures = failure_counts[device.id]

                    device.latency = None

                    print(
                        f"[WARNING] {device.name} "
                        f"({device.ip_address}) "
                        f"ping failed "
                        f"({failures}/{FAILURE_THRESHOLD})"
                    )

                    # Do not declare offline immediately.
                    if failures < FAILURE_THRESHOLD:

                        print(
                            f"[VERIFYING] {device.name} "
                            f"failure not confirmed yet."
                        )

                        continue

                    device.status = "offline"

                    print(
                        f"[DEVICE] {device.name} "
                        f"({device.ip_address}) "
                        f"-> OFFLINE"
                    )

                # ---------------------------------
                # STATUS CHANGE DETECTION
                # ---------------------------------

                new_status = device.status

                if old_status != new_status:

                    print(
                        f"[STATUS CHANGE] "
                        f"{device.name}: "
                        f"{old_status} -> {new_status}"
                    )

                    alert = create_status_alert(
                        db=db,
                        device=device,
                        previous_status=old_status,
                        current_status=new_status
                    )

                    if alert:

                        print(
                            f"[ALERT] "
                            f"{alert.severity} | "
                            f"{alert.event_type} | "
                            f"{device.name}"
                        )

            db.commit()

        except Exception as error:

            db.rollback()

            print(
                f"[MONITOR ERROR] {error}"
            )

        finally:

            db.close()

        await asyncio.sleep(MONITOR_INTERVAL)