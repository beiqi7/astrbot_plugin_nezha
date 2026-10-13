"""哪吒探针（v0 时期魔改版 / nezha-zero 系）API 客户端。

本插件面向 v0 时代的老接口，不是哪吒官方 v1（nezha v1 的 REST 结构完全不同）。
已实测可用的接口：

* ``GET /api/v1/server/details``
  服务器信息 + 硬件 + 实时状态（未传参时返回全部）。
  也支持 ``?tag=分组``，但该模式下 ``display_index`` 全部返回 0（面板顺序丢失），
  且只做大小写敏感的精确匹配，所以插件一律取全量、在本地按分组过滤。
* ``GET /api/v1/monitor/<server_id>``
  该服务器的网络质量监控历史（nezha-zero / 魔改版特有：延迟 + 丢包）。

鉴权：``Authorization: <API Token>``（``Bearer `` 前缀可选，服务端会自动剥离）。
未通过鉴权时 HTTP 状态码仍是 200，需读取响应体的 ``code`` 字段判断。
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Optional

import aiohttp

from astrbot.api import logger

USER_AGENT = "AstrBot-Nezha-Plugin/1.1"

# "AMD EPYC 7551 32-Core Processor 2 Virtual Core"
_CPU_RE = re.compile(r"^(?P<model>.+?)\s+(?P<count>\d+)\s+(?P<kind>Virtual|Physical)\s+Core$")


class NezhaError(Exception):
    """哪吒 API 调用失败。"""


class NezhaAuthError(NezhaError):
    """API Token 无效或权限不足。"""


def _as_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def parse_cpu(cpu_list: Any) -> tuple[str, Optional[int], str]:
    """解析 ``host.CPU``。

    哪吒 agent 生成的是 ``"<型号> <数量> <Virtual|Physical> Core"``：
    agent 侧只有一颗逻辑 CPU 时 ``数量`` 是物理核心数，多路 / 多线程时是逻辑核数。
    返回 ``(型号, 核心数, 物理/虚拟标签)``。
    """
    models: list[str] = []
    cores = 0
    kind = ""
    found = False

    if isinstance(cpu_list, str):
        cpu_list = [cpu_list]
    if not isinstance(cpu_list, (list, tuple)):
        return "", None, ""

    for raw in cpu_list:
        text = str(raw or "").strip()
        if not text:
            continue
        m = _CPU_RE.match(text)
        if m:
            model = m.group("model").strip()
            cores += _as_int(m.group("count"))
            kind = m.group("kind")
            found = True
        else:
            model = text
        if model and model not in models:
            models.append(model)

    return " / ".join(models), (cores or None) if found else None, kind


def _as_str_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v or "").strip()]
    return []


def normalize_server(raw: dict, now: int, online_threshold: int) -> dict:
    """把接口原始条目摊平成插件内部统一结构。

    字段命名统一为小写下划线，避免模板里到处 ``Host.CPU`` / ``Status.CPU`` 混用。
    """
    raw = raw or {}
    host = raw.get("host") or {}
    state = raw.get("status") or {}

    last_active = _as_int(raw.get("last_active"))
    # 面板可能比本地时钟快几秒，负值同样视为“刚刚上报”
    age = now - last_active
    online = bool(last_active) and age <= online_threshold

    cpu_name, cpu_cores, cpu_kind = parse_cpu(host.get("CPU"))

    cpu_labels = [v for v in _as_str_list(host.get("GPU")) if v.lower() not in ("none", "null")]
    temps: list[dict] = []
    for item in state.get("Temperatures") or []:
        if isinstance(item, dict):
            name = str(item.get("Name") or "").strip()
            value = _as_float(item.get("Temperature"), -1.0)
            if value >= 0:
                temps.append({"name": name or "温度", "value": round(value, 1)})

    platform = str(host.get("Platform") or "").strip()
    platform_version = str(host.get("PlatformVersion") or "").strip()

    return {
        # 基础信息
        "id": _as_int(raw.get("id")),
        "name": str(raw.get("name") or "未命名").strip(),
        "tag": str(raw.get("tag") or "").strip(),
        "hidden": bool(raw.get("hide_for_guest")),
        "display_index": _as_int(raw.get("display_index")),
        "last_active": last_active,
        "age": max(0, age),
        "online": online,
        "ipv4": str(raw.get("ipv4") or "").strip(),
        "ipv6": str(raw.get("ipv6") or "").strip(),
        "valid_ip": str(raw.get("valid_ip") or "").strip(),
        "public_note": str(raw.get("PublicNote") or raw.get("public_note") or "").strip(),
        # 硬件
        "platform": platform,
        "platform_version": platform_version,
        "os": f"{platform} {platform_version}".strip(),
        "arch": str(host.get("Arch") or "").strip(),
        "virt": str(host.get("Virtualization") or "").strip(),
        "boot_time": _as_int(host.get("BootTime")),
        "cpu_name": cpu_name,
        "cpu_cores": cpu_cores,
        "cpu_kind": cpu_kind,
        "mem_total": _as_int(host.get("MemTotal")),
        "disk_total": _as_int(host.get("DiskTotal")),
        "swap_total": _as_int(host.get("SwapTotal")),
        "gpu_model": " / ".join(cpu_labels),
        "agent_version": str(host.get("Version") or "").strip(),
        "country": str(host.get("CountryCode") or "").strip().lower(),
        # 实时状态
        "cpu_pct": _as_float(state.get("CPU")),
        "mem_used": _as_int(state.get("MemUsed")),
        "swap_used": _as_int(state.get("SwapUsed")),
        "disk_used": _as_int(state.get("DiskUsed")),
        "net_in_total": _as_int(state.get("NetInTransfer")),
        "net_out_total": _as_int(state.get("NetOutTransfer")),
        "net_in_speed": _as_int(state.get("NetInSpeed")),
        "net_out_speed": _as_int(state.get("NetOutSpeed")),
        "uptime": _as_int(state.get("Uptime")),
        "load1": _as_float(state.get("Load1")),
        "load5": _as_float(state.get("Load5")),
        "load15": _as_float(state.get("Load15")),
        "tcp": _as_int(state.get("TcpConnCount")),
        "udp": _as_int(state.get("UdpConnCount")),
        "procs": _as_int(state.get("ProcessCount")),
        "temps": temps,
        "gpu_pct": _as_float(state.get("GPU")),
    }


def order_servers(servers: list[dict]) -> list[dict]:
    """面板顺序：DisplayIndex 降序，相同则 ID 升序；并写入 1 起的全局序号 ``index``。

    ``index`` 是 ``/nz <序号>`` 的唯一依据，列表 / 分组 / 过滤视图都直接展示它，
    保证用户看到的编号与查询时解析到的节点一致。
    """
    servers.sort(key=lambda s: (-s["display_index"], s["id"]))
    for i, server in enumerate(servers, 1):
        server["index"] = i
    return servers


class NezhaClient:
    """访问哪吒面板的轻量客户端。"""

    def __init__(
        self,
        base_url: str,
        api_token: str = "",
        timeout: float = 10.0,
        show_hidden: bool = True,
        online_threshold: int = 20,
    ):
        self.base_url = self._clean_base(base_url)
        self.api_token = (api_token or "").strip()
        if self.api_token.lower().startswith("bearer "):
            self.api_token = self.api_token[7:].strip()
        self.timeout = max(1.0, float(timeout or 10.0))
        self.show_hidden = bool(show_hidden)
        self.online_threshold = max(1, int(online_threshold or 20))
        self._session: Optional[aiohttp.ClientSession] = None

    @staticmethod
    def _clean_base(base_url: str) -> str:
        base = (base_url or "").strip().rstrip("/")
        # 容忍填写成 https://host/api/v1 或 https://host/api
        for suffix in ("/api/v1", "/api"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
        return base.rstrip("/")

    def configured(self) -> bool:
        return bool(self.base_url)

    def seed(self) -> tuple:
        return (self.base_url, self.api_token, self.timeout, self.show_hidden, self.online_threshold)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT},
                timeout=aiohttp.ClientTimeout(total=self.timeout),
            )
        return self._session

    async def _request(self, path: str) -> Any:
        if not self.configured():
            raise NezhaError("未配置面板地址，请在插件配置中填写 base_url")

        url = f"{self.base_url}{path}"
        headers = {}
        if self.api_token:
            headers["Authorization"] = self.api_token
        session = await self._get_session()
        try:
            async with session.get(url, headers=headers) as resp:
                text = await resp.text()
                status = resp.status
                reason = resp.reason
        except aiohttp.ClientError as e:
            raise NezhaError(f"网络错误: {e}") from e
        except asyncio.TimeoutError as e:
            raise NezhaError(f"请求超时（{self.timeout:g}s）") from e

        if status in (401, 403):
            raise NezhaAuthError(
                f"面板拒绝了这次请求（HTTP {status}）。请检查 api_token 是否为该面板签发的 API Token。"
            )
        if status >= 400:
            raise NezhaError(f"HTTP {status}: {text[:160] or reason}")
        try:
            return json.loads(text)
        except ValueError:
            raise NezhaError(
                f"接口 {path} 返回的不是 JSON（可能是不支持该接口的版本）: {text[:120]}"
            ) from None

    @staticmethod
    def _unwrap(data: Any, path: str) -> list[dict]:
        if not isinstance(data, dict):
            raise NezhaError(f"接口 {path} 返回结构异常")
        code = _as_int(data.get("code"), 0)
        message = str(data.get("message") or "").strip()
        if code == 0:
            result = data.get("result")
            return [x for x in result if isinstance(x, dict)] if isinstance(result, list) else []
        if code in (401, 403):
            raise NezhaAuthError(
                f"面板拒绝了这次请求（code={code}，{message or '访问此接口需要认证'}）。"
                "请检查 api_token 是否为该面板签发的 API Token。"
            )
        raise NezhaError(f"接口 {path} 返回错误：code={code} {message}")

    async def get_servers(self) -> list[dict]:
        """取全部服务器 + 实时状态，按面板顺序排序、编号，并可选过滤隐藏节点。"""
        path = "/api/v1/server/details"
        raw = self._unwrap(await self._request(path), path)
        now = _now()
        servers = [normalize_server(item, now, self.online_threshold) for item in raw]
        if not self.show_hidden:
            servers = [s for s in servers if not s["hidden"]]
        return order_servers(servers)

    async def get_monitor(self, server_id: int) -> list[dict]:
        """取单台服务器的网络质量监控；没有监控或请求失败时返回空列表。"""
        path = f"/api/v1/monitor/{int(server_id)}"
        try:
            return self._unwrap(await self._request(path), path)
        except NezhaError as e:
            logger.debug(f"获取 {path} 失败: {e}")
            return []

    async def get_monitors_bulk(self, server_ids: list[int], concurrency: int = 6) -> dict[int, list[dict]]:
        """并发抓取多台服务器的监控历史，返回 ``{server_id: [...]}``。"""
        if not server_ids:
            return {}
        sem = asyncio.Semaphore(max(1, int(concurrency)))

        async def worker(sid: int) -> tuple[int, list[dict]]:
            async with sem:
                return sid, await self.get_monitor(sid)

        results = await asyncio.gather(*(worker(sid) for sid in server_ids), return_exceptions=True)
        out: dict[int, list[dict]] = {}
        for item in results:
            if isinstance(item, Exception):
                logger.debug(f"批量获取监控失败: {item}")
                continue
            sid, monitors = item
            out[sid] = monitors
        return out


def _now() -> int:
    return int(time.time())


def summarize_monitor(entry: dict, points: int = 60) -> Optional[dict]:
    """把单条监控历史压缩成展示用摘要（只看最近 ``points`` 次探测）。

    哪吒把 ``avg_delay == 0``（或超过面板阈值）视为丢包，此处只把 0 计为丢包。
    """
    created = entry.get("created_at") or []
    delays = entry.get("avg_delay") or []
    if not isinstance(created, (list, tuple)) or not isinstance(delays, (list, tuple)):
        return None
    # 两列按时间对齐；只取两者都有的部分，再截最近 points 个
    end = min(len(created), len(delays))
    if end == 0:
        return None
    start = max(0, end - points) if points and points > 0 else 0
    window = [_as_float(d) for d in delays[start:end]]

    valid = [d for d in window if d > 0]
    total = len(window)
    latest_ms = window[-1]
    return {
        "name": str(entry.get("monitor_name") or "监控").strip(),
        "points": total,
        "loss_pct": round((total - len(valid)) / total * 100, 1),
        "latest": round(latest_ms, 1),
        "latest_ok": latest_ms > 0,
        "avg": round(sum(valid) / len(valid), 1) if valid else 0.0,
        "best": round(min(valid), 1) if valid else 0.0,
        "worst": round(max(valid), 1) if valid else 0.0,
    }


def match_score(node: dict, query: str) -> int:
    """模糊匹配打分：ID / 全局序号 / 名称 / 分组 / IP。分数越高越可信。

    纯数字时 ID 与列表序号同分（100）：两者指向不同节点时由调用方列出候选，
    避免用户照着卡片上的序号查询却被同号 ID 截走。
    """
    q = (query or "").strip().lower()
    if not q:
        return -1
    name = str(node.get("name") or "").lower()
    tag = str(node.get("tag") or "").lower()
    score = -1
    if q.isdigit():
        num = int(q)
        if num == node.get("id") or num == node.get("index"):
            score = 100
    if q == name:
        score = max(score, 100)
    elif name.startswith(q):
        score = max(score, 85)
    elif q in name:
        score = max(score, 75)
    if q == tag:
        score = max(score, 90)
    elif tag and q in tag:
        score = max(score, 70)
    if q in str(node.get("ipv4") or "").lower() or q in str(node.get("ipv6") or "").lower():
        score = max(score, 65)
    return score


def find_nodes(nodes: list[dict], query: str, limit: int = 8) -> list[tuple[int, dict]]:
    """返回按匹配度排序的 ``(分数, 节点)``，同分按全局序号。"""
    scored = [(match_score(n, query), n) for n in nodes]
    scored = [item for item in scored if item[0] >= 0]
    scored.sort(key=lambda x: (-x[0], x[1]["index"]))
    return scored[:limit]
