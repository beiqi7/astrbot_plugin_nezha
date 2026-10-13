"""AstrBot 插件：哪吒探针（v0 魔改版 / nezha-zero 系）服务器监控。

指令：/nz（别名 /nezha、/哪吒、/探针）—— 概况 / 列表 / 分组 / 单机详情。
卡片走 AstrBot 的文转图（Jinja2 + HTML），在 NapCat 等 OneBot 适配器下以图片消息发出。
"""

from __future__ import annotations

import asyncio
import re
import time

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .cards import (
    DEFAULT_BG_URL,
    TMPL_DETAIL,
    TMPL_GROUP,
    TMPL_LIST,
    TMPL_SUMMARY,
    build_detail_data,
    build_group_data,
    build_list_data,
    build_summary_data,
    normalize_quality,
    screenshot_options,
    visible_nodes,
)
from .formatter import (
    ICON_DENY,
    ICON_FAIL,
    ICON_WARN,
    filter_by_tag,
    format_group,
    format_help,
    format_list,
    format_node,
    format_summary,
)
from .nezha_client import (
    NezhaAuthError,
    NezhaClient,
    NezhaError,
    find_nodes,
    summarize_monitor,
)

COMMAND_NAMES = {"nz", "nezha", "哪吒", "探针"}
HELP_SUBS = {"help", "h", "?", "帮助", "菜单"}
LIST_SUBS = {"list", "ls", "列表"}
GROUP_SUBS = {"group", "grp", "g", "groups", "分类", "分组"}
INFO_SUBS = {"info", "status", "st", "信息", "状态", "详情"}
SID_SUBS = {"sid", "id", "我的id"}


@register(
    "astrbot_plugin_nezha",
    "serenite",
    "哪吒探针（v0 魔改版）：服务器概况 / 列表 / 分组 / 单机详情卡片",
    "1.1.0",
)
class NezhaPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config or {}
        self.client = self._build_client()

    # ---------------- 配置 ----------------

    def _build_client(self) -> NezhaClient:
        return NezhaClient(
            base_url=str(self.config.get("base_url", "") or ""),
            api_token=str(self.config.get("api_token", "") or ""),
            timeout=float(self.config.get("timeout", 10) or 10),
            show_hidden=bool(self.config.get("show_hidden", True)),
            online_threshold=int(self.config.get("online_threshold", 20) or 20),
        )

    def _reload_client(self) -> None:
        """配置热更新：AstrBot 后台改完配置无需重载插件。"""
        new = self._build_client()
        if new.seed() == self.client.seed():
            return
        old = self.client
        self.client = new
        try:
            asyncio.get_running_loop().create_task(old.close())
        except RuntimeError:  # 没有运行中的事件循环，直接丢弃旧会话
            pass

    def _use_card(self) -> bool:
        return str(self.config.get("output_mode", "card") or "card").lower() != "text"

    def _quality(self) -> str:
        return normalize_quality(str(self.config.get("image_quality", "high") or "high"))

    def _max_rows(self) -> int:
        try:
            return max(0, int(self.config.get("max_list_rows", 60) or 0))
        except (TypeError, ValueError):
            return 60

    def _monitor_enabled(self) -> bool:
        return bool(self.config.get("enable_monitor", True))

    def _monitor_in_list(self) -> bool:
        return bool(self.config.get("monitor_in_list", False))

    def _monitor_points(self) -> int:
        try:
            return max(1, int(self.config.get("monitor_points", 60) or 60))
        except (TypeError, ValueError):
            return 60

    def _bg_url(self) -> str:
        """二次元背景图接口；带时间戳避免文转图缓存命中同一张。"""
        base = str(self.config.get("bg_url", "") or DEFAULT_BG_URL).strip() or DEFAULT_BG_URL
        base = base.rstrip("/")
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}_t={int(time.time() * 1000)}"

    def _common_data(self, data: dict) -> dict:
        out = dict(data)
        out["bg_url"] = self._bg_url()
        out["base_url"] = self.client.base_url or "-"
        out["fetched_at"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        return out

    # ---------------- 权限 ----------------

    def _whitelist_ids(self) -> set:
        raw = str(self.config.get("allowed_users", "") or "")
        return {p.strip() for p in re.split(r"[\s,;，；]+", raw) if p.strip()}

    def _check_permission(self, event: AstrMessageEvent) -> tuple:
        mode = str(self.config.get("permission_mode", "all") or "all").lower()
        if mode in ("", "all", "everyone", "public"):
            return True, ""

        sender = str(event.get_sender_id() or "")
        try:
            is_admin = bool(event.is_admin())
        except Exception:
            is_admin = False

        if mode in ("admin", "admins", "管理员"):
            if is_admin:
                return True, ""
            return False, f"{ICON_DENY} 此指令仅 AstrBot 管理员可用。"

        if mode in ("whitelist", "wl", "白名单"):
            if is_admin or (sender and sender in self._whitelist_ids()):
                return True, ""
            return (
                False,
                f"{ICON_DENY} 你不在白名单中，无法使用此指令。\n"
                "（管理员可在插件配置里添加 allowed_users，或用 /nz sid 查看自己的 ID）",
            )
        return True, ""

    # ---------------- 生命周期 ----------------

    async def initialize(self):
        if self.client.configured():
            logger.info(f"哪吒探针插件已加载：{self.client.base_url}")
        else:
            logger.warning("哪吒探针插件未配置 base_url，请在后台填写")

    async def terminate(self):
        await self.client.close()

    # ---------------- 参数 / 输出 ----------------

    def _parse_args(self, event: AstrMessageEvent) -> list:
        text = (event.message_str or "").strip()
        if not text:
            return []
        parts = text.split()
        if parts:
            head = parts[0].lstrip("/!！.．").lower()
            if head in COMMAND_NAMES:
                parts = parts[1:]
        return parts

    async def _render_card(self, tmpl: str, data: dict):
        try:
            return await self.html_render(tmpl, data, options=screenshot_options(self._quality()))
        except Exception as e:
            logger.warning(f"卡片渲染失败，回退文本: {e}")
            return None

    async def _reply(self, event: AstrMessageEvent, tmpl: str, data: dict, text: str):
        if self._use_card():
            url = await self._render_card(tmpl, self._common_data(data))
            if url:
                yield event.image_result(url)
                return
        yield event.plain_result(text)

    def _config_hint(self) -> str:
        return (
            f"{ICON_WARN} 未配置面板地址。\n"
            "请到 AstrBot 后台 → 插件 → 哪吒探针 填写 base_url 与 api_token。"
        )

    async def _fetch_monitors(self, nodes: list, enabled: bool) -> dict:
        """按需并发抓取在线服务器的网络质量监控摘要（只传入实际会显示的节点）。"""
        if not enabled:
            return {}
        ids = [n["id"] for n in nodes if n.get("online")]
        if not ids:
            return {}
        raw = await self.client.get_monitors_bulk(ids)
        points = self._monitor_points()
        out = {}
        for sid, entries in raw.items():
            summaries = []
            for entry in entries:
                summary = summarize_monitor(entry, points=points)
                if summary:
                    summaries.append(summary)
            if summaries:
                out[sid] = summaries
        return out

    # ---------------- 指令 ----------------

    @filter.command("nz", alias={"nezha", "哪吒", "探针"})
    async def nz_cmd(self, event: AstrMessageEvent):
        """哪吒探针：概况 / 列表 / 分组 / 单机详情"""
        self._reload_client()

        ok, deny_msg = self._check_permission(event)
        if not ok:
            yield event.plain_result(deny_msg)
            return

        args = self._parse_args(event)
        sub = args[0].lower() if args else ""
        rest = " ".join(args[1:]).strip()

        if sub in SID_SUBS:
            yield event.plain_result(f"你的用户 ID：{event.get_sender_id()}")
            return

        if sub in HELP_SUBS:
            yield event.plain_result(format_help("nz"))
            return

        if not self.client.configured():
            yield event.plain_result(self._config_hint())
            return

        try:
            if not args:
                async for m in self._cmd_summary(event):
                    yield m
            elif sub in LIST_SUBS:
                async for m in self._cmd_list(event, rest):
                    yield m
            elif sub in GROUP_SUBS:
                async for m in self._cmd_group(event, rest):
                    yield m
            elif sub in INFO_SUBS:
                if not rest:
                    yield event.plain_result("用法：/nz <名称|ID|序号>")
                    return
                async for m in self._cmd_one(event, rest):
                    yield m
            else:
                async for m in self._cmd_one(event, " ".join(args).strip()):
                    yield m
        except NezhaAuthError as e:
            logger.error(f"哪吒鉴权失败: {e}")
            yield event.plain_result(f"{ICON_DENY} {e}")
        except NezhaError as e:
            logger.error(f"哪吒请求失败: {e}")
            yield event.plain_result(f"{ICON_FAIL} 请求失败：{e}")
        except Exception as e:  # pragma: no cover - 兜底，避免指令静默失败
            logger.exception("哪吒探针插件异常")
            yield event.plain_result(f"{ICON_FAIL} 插件错误：{e}")

    async def _cmd_summary(self, event: AstrMessageEvent):
        nodes = await self.client.get_servers()
        data = build_summary_data(nodes)
        text = format_summary(nodes)
        async for m in self._reply(event, TMPL_SUMMARY, data, text):
            yield m

    async def _cmd_list(self, event: AstrMessageEvent, tag: str):
        # 始终取全量再本地过滤：面板 ?tag= 会丢失排序且大小写敏感，序号也会与 /nz <序号> 对不上
        nodes = filter_by_tag(await self.client.get_servers(), tag)
        if not nodes:
            yield event.plain_result(
                f"未找到分组「{tag}」的服务器。\n发送 /nz group 查看所有分组。"
                if tag
                else "面板没有返回任何服务器。"
            )
            return
        max_rows = self._max_rows()
        monitors = await self._fetch_monitors(
            visible_nodes(nodes, max_rows, grouped=False), self._monitor_in_list()
        )
        data = build_list_data(nodes, monitors, max_rows=max_rows, tag=tag)
        text = format_list(nodes, max_rows=max_rows, tag=tag)
        async for m in self._reply(event, TMPL_LIST, data, text):
            yield m

    async def _cmd_group(self, event: AstrMessageEvent, tag: str):
        nodes = await self.client.get_servers()
        if not nodes:
            yield event.plain_result("面板没有返回任何服务器。")
            return
        nodes = filter_by_tag(nodes, tag)
        if not nodes:
            yield event.plain_result(f"未找到分组「{tag}」。\n发送 /nz group 查看所有分组。")
            return
        max_rows = self._max_rows()
        monitors = await self._fetch_monitors(
            visible_nodes(nodes, max_rows, grouped=True), self._monitor_in_list()
        )
        data = build_group_data(nodes, tag, monitors, max_rows=max_rows)
        text = format_group(nodes, tag, max_rows=max_rows)
        async for m in self._reply(event, TMPL_GROUP, data, text):
            yield m

    async def _cmd_one(self, event: AstrMessageEvent, query: str):
        nodes = await self.client.get_servers()
        if not nodes:
            yield event.plain_result("面板没有返回任何服务器。")
            return

        hits = find_nodes(nodes, query, limit=8)
        if not hits:
            yield event.plain_result(
                f"未找到「{query}」。\n"
                "支持模糊匹配名称 / 分组 / ID / 列表序号 / IP，发送 /nz list 查看列表。"
            )
            return

        # 最高分并列（含「序号 N」与「ID N」指向不同节点）：只列并列的候选让用户写明，避免误匹配
        tied = [n for s, n in hits if s == hits[0][0]]
        if len(tied) > 1:
            lines = [f"找到多个与「{query}」相关的服务器，请写具体一点：", "──────────────"]
            for n in tied:
                tag = f" · {n['tag']}" if n.get("tag") else ""
                lines.append(f"#{n['index']} {n['name']}{tag}（ID {n['id']}）")
            lines.append("──────────────")
            lines.append("#序号 即 /nz list 里的编号；写完整节点名最准确")
            if query.strip().lower() in {str(n.get("tag") or "").strip().lower() for n in nodes}:
                lines.append(f"这是分组名，想看整组请用：/nz group {query.strip()}")
            yield event.plain_result("\n".join(lines))
            return

        node = hits[0][1]
        monitors = await self._fetch_monitors([node], self._monitor_enabled())
        data = build_detail_data(node, monitors.get(node["id"]))
        text = format_node(node, monitors.get(node["id"]))
        async for m in self._reply(event, TMPL_DETAIL, data, text):
            yield m
