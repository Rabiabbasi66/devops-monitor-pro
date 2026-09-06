from typing import List, Optional

from beanie import PydanticObjectId
from beanie.odm.operators.find.comparison import In

from ..models.server import Server, ServerStatus
from ..schemas.server import ServerCreate
from ..utils.security import generate_agent_token


class ServerRepository:
    async def create(self, data: ServerCreate, user_id: str) -> Server:
        server = Server(
            name=data.name,
            ip_address=data.ip_address,
            server_type=data.server_type,
            tags=data.tags,
            user_id=user_id,
            agent_token=generate_agent_token(),
        )
        await server.insert()
        return server

    async def list_for_user(
        self,
        user_id: str,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
        admin: bool = False,
    ) -> List[Server]:
        query = Server.find() if admin else Server.find(Server.user_id == user_id)
        if status:
            query = query.find(Server.status == status)
        return await query.skip(skip).limit(limit).to_list()

    async def get_by_id(
        self, server_id: str, user_id: Optional[str] = None, admin: bool = False
    ) -> Optional[Server]:
        try:
            oid = PydanticObjectId(server_id)
        except Exception:
            return None
        if admin:
            return await Server.get(oid)
        return await Server.find_one(Server.id == oid, Server.user_id == user_id)

    async def get_by_agent_token(self, token: str) -> Optional[Server]:
        return await Server.find_one(Server.agent_token == token)

    async def get_by_ids(self, server_ids: List[str]) -> List[Server]:
        if not server_ids:
            return []
        oids = []
        for sid in server_ids:
            try:
                oids.append(PydanticObjectId(sid))
            except Exception:
                continue
        if not oids:
            return []
        return await Server.find(In(Server.id, oids)).to_list()

    async def delete(self, server: Server) -> None:
        await server.delete()

    async def count_all(self, user_id: Optional[str] = None, admin: bool = False) -> int:
        if admin:
            return await Server.find().count()
        return await Server.find(Server.user_id == user_id).count()

    async def list_stale(self, cutoff) -> List[Server]:
        return await Server.find(
            Server.last_seen != None,  # noqa: E711
            Server.last_seen < cutoff,
            Server.health_status != ServerStatus.UNKNOWN,
        ).to_list()
