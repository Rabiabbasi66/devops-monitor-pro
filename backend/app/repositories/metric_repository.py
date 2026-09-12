from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import settings
from ..models.metric import Metric
from ..schemas.metric import MetricIngest


class MetricRepository:
    async def create(self, data: MetricIngest) -> Metric:
        metric = Metric(
            server_id=data.server_id,
            cpu_usage=data.cpu_usage,
            cpu_count=data.cpu_count,
            cpu_physical=data.cpu_physical,
            cpu_frequency=data.cpu_frequency,
            cpu_per_core=data.cpu_per_core,
            memory_usage=data.memory_usage,
            memory_used=data.memory_used,
            memory_available=data.memory_available,
            memory_total=data.memory_total,
            memory_free=data.memory_free,
            swap_total=data.swap_total,
            swap_used=data.swap_used,
            swap_percent=data.swap_percent,
            disk_usage=data.disk_usage,
            disk_used=data.disk_used,
            disk_available=data.disk_available,
            disk_total=data.disk_total,
            disk_read_bytes=data.disk_read_bytes,
            disk_write_bytes=data.disk_write_bytes,
            disk_read_count=data.disk_read_count,
            disk_write_count=data.disk_write_count,
            network_received=data.network_received,
            network_sent=data.network_sent,
            packets_sent=data.packets_sent,
            packets_received=data.packets_received,
            errors_in=data.errors_in,
            errors_out=data.errors_out,
            dropped_in=data.dropped_in,
            dropped_out=data.dropped_out,
            network_interfaces=data.network_interfaces,
            uptime=data.uptime,
            load_average=data.load_average,
            hostname=data.hostname,
            operating_system=data.operating_system,
            os_version=data.os_version,
            architecture=data.architecture,
            platform=data.platform,
            python_version=data.python_version,
            boot_time=data.boot_time,
            processes=data.processes,
            response_time_ms=data.response_time_ms,
        )
        await metric.insert()
        return metric

    async def get_latest(self, server_id: str) -> Optional[Metric]:
        return await Metric.find(Metric.server_id == server_id).sort(
            -Metric.timestamp
        ).limit(1).first_or_none()

    async def list_for_server(
        self,
        server_id: str,
        hours: int = 24,
        limit: int = 100,
        skip: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[Metric]:
        filters = [Metric.server_id == server_id]
        if start_time:
            filters.append(Metric.timestamp >= start_time)
        if end_time:
            filters.append(Metric.timestamp <= end_time)
        if not start_time and not end_time:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            filters.append(Metric.timestamp >= cutoff)
        return await Metric.find(*filters).sort(-Metric.timestamp).skip(skip).limit(limit).to_list()

    async def aggregate(
        self, server_id: str, hours: int = 24
    ) -> Dict[str, Any]:
        metrics = await self.list_for_server(server_id, hours=hours, limit=5000)
        if not metrics:
            return {
                "cpu_avg": 0,
                "cpu_max": 0,
                "cpu_min": 0,
                "memory_avg": 0,
                "memory_max": 0,
                "memory_min": 0,
                "disk_avg": 0,
                "disk_max": 0,
                "disk_min": 0,
            }
        return {
            "cpu_avg": sum(m.cpu_usage for m in metrics) / len(metrics),
            "cpu_max": max(m.cpu_usage for m in metrics),
            "cpu_min": min(m.cpu_usage for m in metrics),
            "memory_avg": sum(m.memory_usage for m in metrics) / len(metrics),
            "memory_max": max(m.memory_usage for m in metrics),
            "memory_min": min(m.memory_usage for m in metrics),
            "disk_avg": sum(m.disk_usage for m in metrics) / len(metrics),
            "disk_max": max(m.disk_usage for m in metrics),
            "disk_min": min(m.disk_usage for m in metrics),
        }

    async def cleanup_old(self) -> int:
        cutoff = datetime.utcnow() - timedelta(days=settings.METRIC_RETENTION_DAYS)
        result = await Metric.find(Metric.timestamp < cutoff).delete()
        return result.deleted_count if result else 0

    async def count_for_server(
        self,
        server_id: str,
        hours: int = 24,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> int:
        filters = [Metric.server_id == server_id]
        if start_time:
            filters.append(Metric.timestamp >= start_time)
        if end_time:
            filters.append(Metric.timestamp <= end_time)
        if not start_time and not end_time:
            cutoff = datetime.utcnow() - timedelta(hours=hours)
            filters.append(Metric.timestamp >= cutoff)
        return await Metric.find(*filters).count()
