"""System information utilities for JARVIS.

Provides a snapshot of hardware and OS details using psutil and platform.
All data is read‑only and safe – no privileged actions are performed.
"""

from __future__ import annotations

import platform
import time
from typing import Dict, Any

import psutil


def get_system_snapshot() -> Dict[str, Any]:
    """Collect a snapshot of key system properties."""
    boot_ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(psutil.boot_time()))
    uptime_sec = int(time.time() - psutil.boot_time())
    hours, rem = divmod(uptime_sec, 3600)
    minutes, _ = divmod(rem, 60)

    vm = psutil.virtual_memory()
    du = psutil.disk_usage("C:\\" if platform.system() == "Windows" else "/")

    snapshot = {
        "computer_name": platform.node(),
        "windows_version": f"{platform.release()} ({platform.version()})",
        "os": f"Windows {platform.release()} ({platform.version()})",
        "processor": platform.processor() or "x86_64",
        "boot_time": boot_ts,
        "uptime_human": f"{hours}h {minutes}m",
        "cpu_count_logical": psutil.cpu_count(logical=True) or 1,
        "cpu_usage_percent": round(psutil.cpu_percent(interval=None), 1),
        "ram_total_gb": round(vm.total / (1024 ** 3), 2),
        "ram_used_gb": round(vm.used / (1024 ** 3), 2),
        "ram_usage_percent": round(vm.percent, 1),
        "disk_total_gb": round(du.total / (1024 ** 3), 2),
        "disk_used_gb": round(du.used / (1024 ** 3), 2),
        "disk_free_gb": round(du.free / (1024 ** 3), 2),
        "disk_percent": round(du.percent, 1),
    }

    battery = psutil.sensors_battery()
    if battery is not None:
        snapshot["battery_present"] = True
        snapshot["battery_percent"] = round(battery.percent, 1)
        snapshot["battery_plugged_in"] = bool(battery.power_plugged)
    else:
        snapshot["battery_present"] = False
        snapshot["battery_percent"] = 100
        snapshot["battery_plugged_in"] = True

    # Drives info
    drives = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            drives.append({
                "device": part.device,
                "mountpoint": part.mountpoint,
                "free_gb": round(usage.free / (1024 ** 3), 1),
                "percent_used": round(usage.percent, 1),
            })
        except Exception:
            continue
    snapshot["drives"] = drives

    return snapshot


def get_system_summary() -> Dict[str, Any]:
    """Alias for get_system_snapshot."""
    return get_system_snapshot()
