import psutil


def collect_cpu() -> float:
    return psutil.cpu_percent(interval=1)


def collect_memory() -> dict:
    mem = psutil.virtual_memory()
    return {
        "memory_usage": mem.percent,
        "memory_used": float(mem.used),
        "memory_available": float(mem.available),
    }


def collect_disk() -> dict:
    disk = psutil.disk_usage("/")
    return {
        "disk_usage": disk.percent,
        "disk_used": float(disk.used),
        "disk_available": float(disk.free),
    }


def collect_network() -> dict:
    net = psutil.net_io_counters()
    return {
        "network_sent": float(net.bytes_sent),
        "network_received": float(net.bytes_recv),
    }


def collect_system() -> dict:
    import platform
    import time

    boot = psutil.boot_time()
    uptime = time.time() - boot
    load_avg = None
    if hasattr(psutil, "getloadavg"):
        try:
            load_avg = psutil.getloadavg()[0]
        except (OSError, AttributeError):
            load_avg = None
    return {
        "hostname": platform.node(),
        "operating_system": f"{platform.system()} {platform.release()}",
        "uptime": uptime,
        "load_average": load_avg,
    }


def collect_processes() -> int:
    return len(psutil.pids())

