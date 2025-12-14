import uuid
from datetime import datetime

import httpx

from app.core.config import settings
from app.service.cache import get_servisedef_id


class SolrLoggerClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient()

    async def log_event(self, audit_record: dict) -> None:
        url = f"{self.base_url}/update?commit=true"
        headers = {"Content-Type": "application/json"}
        await self._client.post(url, json=[audit_record], headers=headers)

    async def aclose(self):
        await self._client.aclose()

    def build_audit_record(
        self,
        *,
        policy: int,
        policyVersion: int,
        access: str,
        repo: str,
        sess: str,
        reqUser: str,
        resource: str,
        cliIP: str,
        result: int,
        agentHost: str,
        action: str,
        seq_num: int = 1,
        event_count: int = 1,
        event_dur_ms: int = 0,
        logType: str = "RangerAudit",
        resType: str = "path",
        reason: str = "",
        tags: list = None,
        cluster: str = "",
        zone: str = ""
    ) -> dict:
        if tags is None:
            tags = []
        servicedef_id = get_servisedef_id(settings.RANGER_SERVICEDEF_NAME)
        evtTime = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        return {
            "id": str(uuid.uuid4()),
            "evtTime": evtTime,
            "policy": policy,
            "policyVersion": policyVersion,
            "access": access,
            "enforcer": "ranger-acl",
            "repo": repo,
            "repoType": servicedef_id or 1,
            "sess": sess,
            "reqUser": reqUser,
            "resource": resource,
            "cliIP": cliIP,
            "result": result,
            "agentHost": agentHost,
            "logType": logType,
            "resType": resType,
            "reason": reason,
            "action": action,
            "seq_num": seq_num,
            "event_count": event_count,
            "event_dur_ms": event_dur_ms,
            "tags": tags,
            "cluster": cluster,
            "zone": zone,
        }
