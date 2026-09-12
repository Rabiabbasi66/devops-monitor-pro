import os
import platform
import psutil
import time


def collect_cpu() -> dict:
    """Collect detailed CPU metrics."""
    cpu_count = psutil.cpu_count(logical=True)
    cpu_physical = psutil.cpu_count(logical=False)
    cpu_freq = None
    try:
        freq = psutil.cpu_freq()
        if freq:
            cpu_freq = freq.current
    except (OSError, AttributeError):
        pass
    
    cpu_percent = psutil.cpu_percent(interval=1)
    
    # Per-core CPU usage (limited to first 8 cores to avoid excessive data)
    cpu_per_core = []
    try:
        per_core = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_per_core = per_core[:8]  # Limit to first 8 cores
    except (OSError, AttributeError):
        pass
    
    return {
        "cpu_usage": cpu_percent,
        "cpu_count": cpu_count,
        "cpu_physical": cpu_physical,
        "cpu_frequency": cpu_freq,
        "cpu_per_core": cpu_per_core,
    }


def collect_memory() -> dict:
    """Collect detailed memory metrics including swap."""
    mem = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    return {
        "memory_usage": mem.percent,
        "memory_used": float(mem.used),
        "memory_available": float(mem.available),
        "memory_total": float(mem.total),
        "memory_free": float(mem.free),
        "swap_total": float(swap.total),
        "swap_used": float(swap.used),
        "swap_percent": swap.percent,
    }


def _get_disk_path() -> str:
    """Return the root disk path appropriate for the current platform."""
    if platform.system() == "Windows":
        # Use the drive letter of the current working directory (e.g. "C:\\")
        drive, _ = os.path.splitdrive(os.path.abspath("."))
        return drive + "\\"
    return "/"


def collect_disk() -> dict:
    """Collect detailed disk metrics including I/O."""
    disk = psutil.disk_usage(_get_disk_path())
    
    # Disk I/O metrics
    disk_io = None
    try:
        disk_io = psutil.disk_io_counters()
    except (OSError, AttributeError):
        pass
    
    result = {
        "disk_usage": disk.percent,
        "disk_used": float(disk.used),
        "disk_available": float(disk.free),
        "disk_total": float(disk.total),
    }
    
    if disk_io:
        result.update({
            "disk_read_bytes": float(disk_io.read_bytes),
            "disk_write_bytes": float(disk_io.write_bytes),
            "disk_read_count": disk_io.read_count,
            "disk_write_count": disk_io.write_count,
        })
    
    return result


def collect_network() -> dict:
    """Collect detailed network metrics including packet counts."""
    net = psutil.net_io_counters()
    
    # Network interfaces info
    interfaces = {}
    try:
        for name, stats in psutil.net_io_counters(pernic=True).items():
            interfaces[name] = {
                "bytes_sent": float(stats.bytes_sent),
                "bytes_recv": float(stats.bytes_recv),
                "packets_sent": stats.packets_sent,
                "packets_recv": stats.packets_recv,
                "errin": stats.errin,
                "errout": stats.errout,
                "dropin": stats.dropin,
                "dropout": stats.dropout,
            }
    except (OSError, AttributeError):
        pass
    
    result = {
        "network_sent": float(net.bytes_sent),
        "network_received": float(net.bytes_recv),
        "packets_sent": net.packets_sent,
        "packets_received": net.packets_recv,
        "errors_in": net.errin,
        "errors_out": net.errout,
        "dropped_in": net.dropin,
        "dropped_out": net.dropout,
    }
    
    # Add interfaces if available (limit to first 5 to avoid excessive data)
    if interfaces:
        result["network_interfaces"] = dict(list(interfaces.items())[:5])
    
    return result


def collect_system() -> dict:
    """Collect detailed system information."""
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
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "uptime": uptime,
        "load_average": load_avg,
        "boot_time": boot,
    }


def collect_processes() -> dict:
    """Collect top processes by CPU and memory."""
    processes = []
    
    try:
        # Get all processes and sort by CPU usage
        all_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
            try:
                all_procs.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Sort by CPU usage and get top 5
        top_cpu = sorted(all_procs, key=lambda x: x.get('cpu_percent', 0) or 0, reverse=True)[:5]
        # Sort by memory usage and get top 5
        top_memory = sorted(all_procs, key=lambda x: x.get('memory_percent', 0) or 0, reverse=True)[:5]
        
        processes = {
            "total": len(all_procs),
            "top_cpu": top_cpu,
            "top_memory": top_memory,
        }
    except (OSError, AttributeError):
        processes = {
            "total": len(psutil.pids()),
            "top_cpu": [],
            "top_memory": [],
        }
    
    return processes
