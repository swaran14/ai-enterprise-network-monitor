import asyncio
from datetime import datetime

from backend.database import SessionLocal
from backend.models import Device
from monitoring.ping_monitor import ping_device
from alerts.alert_service import (
    create_status_alert,
    create_performance_alert
)


MONITOR_INTERVAL = 15

# Number of consecutive failures required
# before declaring a device offline.
FAILURE_THRESHOLD = 3
# Performance monitoring configuration
HIGH_LATENCY_THRESHOLD = 100
HIGH_LATENCY_COUNT_THRESHOLD = 3

# Consecutive high-latency readings per device
high_latency_counts = {}

# Devices with a confirmed performance incident
performance_degraded = set()

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
                    # LATENCY / PERFORMANCE MONITORING
                    # ---------------------------------
                    latency = result["latency"]

                    if (
                        latency is not None
                        and latency > HIGH_LATENCY_THRESHOLD
                    ):
                        current_latency_count = high_latency_counts.get(
                            device.id,
                            0
                        )

                        if current_latency_count < HIGH_LATENCY_COUNT_THRESHOLD:
                            current_latency_count += 1

                        high_latency_counts[device.id] = current_latency_count

                        print(
                            f"[PERFORMANCE WARNING] "
                            f"{device.name} high latency "
                            f"{latency} ms "
                            f"({current_latency_count}/"
                            f"{HIGH_LATENCY_COUNT_THRESHOLD})"
                        )

                        # Confirm degradation only after 3 consecutive readings
                        if (
                            current_latency_count >= HIGH_LATENCY_COUNT_THRESHOLD
                            and device.id not in performance_degraded
                        ):
                            performance_degraded.add(device.id)

                            performance_alert = create_performance_alert(
                                db=db,
                                device=device,
                                event_type="PERFORMANCE_DEGRADED"
                            )

                            if performance_alert:
                                print(
                                    f"[PERFORMANCE ALERT] "
                                    f"{performance_alert.severity} | "
                                    f"{performance_alert.event_type} | "
                                    f"{device.name}"
                                )

                    else:
                        # Latency returned to normal
                        high_latency_counts[device.id] = 0

                        if device.id in performance_degraded:
                            performance_degraded.remove(device.id)

                            recovery_alert = create_performance_alert(
                                db=db,
                                device=device,
                                event_type="PERFORMANCE_RECOVERED"
                            )

                            if recovery_alert:
                                print(
                                    f"[PERFORMANCE RECOVERY] "
                                    f"{recovery_alert.severity} | "
                                    f"{recovery_alert.event_type} | "
                                    f"{device.name}"
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
                    # Offline checks must not count toward consecutive high latency.
                    high_latency_counts[device.id] = 0

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