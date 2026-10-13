"""二次元玻璃拟态卡片模板（概况 / 列表 / 单机 / 分组）。

设计语言沿用 astrbot_plugin_komari 的玻璃拟态卡片，但数据全部来自哪吒面板。
模板宽度即内容宽度（960 / 900 px），清晰度走文转图服务的
`device_scale_factor_level`（已实测官方 t2i 服务会按 1.0 / 1.3 / 1.8 倍真实提升渲染分辨率，
比截图后放大更锐利；服务若不支持该参数则退化为 1x，不影响可用性）。
"""

from __future__ import annotations

from typing import Any, Optional

from .formatter import (
    cores_label,
    cpu_label,
    flag_emoji,
    group_by_tag,
    human_age,
    human_bytes,
    human_delay,
    human_speed,
    human_time,
    human_uptime,
    limit_rows,
    percent,
    tag_of,
)

# 内容宽度（与 CSS 一致）
WIDTH_SUMMARY = 960
WIDTH_LIST = 960
WIDTH_DETAIL = 900
WIDTH_GROUP = 960

DEFAULT_BG_URL = "https://mygo.pp.ua/"

QUALITY_LEVELS = ("normal", "high", "ultra")
DEFAULT_QUALITY = "high"


def normalize_quality(quality: str) -> str:
    """非法值一律回退到默认清晰度 high（与 _conf_schema.json 一致）。"""
    level = (quality or "").strip().lower()
    return level if level in QUALITY_LEVELS else DEFAULT_QUALITY


def screenshot_options(quality: str = DEFAULT_QUALITY) -> dict:
    """文转图参数。

    ``device_scale_factor_level`` 是 AstrBot 文转图服务支持的清晰度参数
    （normal=1.0x / high=1.3x / ultra=1.8x 真实渲染分辨率）；
    其余只用文档认可的 Playwright 截图参数。
    """
    return {
        "full_page": True,
        "type": "png",
        "device_scale_factor_level": normalize_quality(quality),
    }


def _short(value: Any, limit: int = 42) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in ("none", "null", "-"):
        return ""
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _temp_label(temps: list[dict]) -> str:
    if not temps:
        return ""
    return " · ".join(f"{t['name']} {t['value']:.0f}°C" for t in temps[:3])


def _pick_delay(monitors: Optional[list[dict]]) -> Optional[dict]:
    """列表里的「延迟」列取该服务器最优的一条监控：
    先看丢包最低，再看延迟最低；全部超时则退回第一条。"""
    if not monitors:
        return None
    reachable = [m for m in monitors if float(m.get("latest") or 0) > 0]
    if reachable:
        return min(
            reachable,
            key=lambda m: (float(m.get("loss_pct") or 0), float(m.get("latest") or 0)),
        )
    return monitors[0]


def build_node_view(node: dict, monitors: Optional[list[dict]] = None) -> dict:
    """把内部节点结构转成模板直接可用的展示结构。"""
    online = bool(node.get("online"))
    cpu = float(node.get("cpu_pct") or 0) if online else 0.0
    ram_used = node.get("mem_used") or 0
    ram_total = node.get("mem_total") or 0
    disk_used = node.get("disk_used") or 0
    disk_total = node.get("disk_total") or 0
    swap_used = node.get("swap_used") or 0
    swap_total = node.get("swap_total") or 0
    ram_p = percent(ram_used, ram_total) if online else 0.0
    disk_p = percent(disk_used, disk_total) if online else 0.0
    swap_p = percent(swap_used, swap_total) if online and swap_total else 0.0

    loads = "-"
    if online:
        loads = (
            f"{float(node.get('load1') or 0):.2f} / "
            f"{float(node.get('load5') or 0):.2f} / "
            f"{float(node.get('load15') or 0):.2f}"
        )

    best = _pick_delay(monitors)
    monitor_rows = []
    for m in monitors or []:
        monitor_rows.append(
            {
                "name": m.get("name") or "监控",
                "latest": human_delay(m.get("latest")),
                "latest_ok": bool(m.get("latest_ok")),
                "loss_pct": f"{float(m.get('loss_pct') or 0):.1f}",
                "loss_bad": float(m.get("loss_pct") or 0) > 0,
                "avg": human_delay(m.get("avg")),
                "best": human_delay(m.get("best")),
                "worst": human_delay(m.get("worst")),
                "points": m.get("points") or 0,
            }
        )

    return {
        "index": node.get("index", 0),
        "id": node.get("id"),
        "name": node.get("name") or "未命名",
        "tag": tag_of(node),
        "flag": flag_emoji(node.get("country")),
        "online": online,
        "status_text": "在线" if online else "离线",
        "last_active": human_age(node.get("age")),
        "hidden": bool(node.get("hidden")),
        # CPU / 内存 / 磁盘 / 交换
        "cpu": round(cpu, 1),
        "cpu_w": round(min(100.0, max(0.0, cpu)), 1),
        "cpu_name": _short(node.get("cpu_name"), 60) or "-",
        "cores_label": cores_label(node),
        "cpu_label": _short(cpu_label(node), 60),
        "ram_p": round(ram_p, 1),
        "ram_w": round(min(100.0, max(0.0, ram_p)), 1),
        "disk_p": round(disk_p, 1),
        "disk_w": round(min(100.0, max(0.0, disk_p)), 1),
        "swap_p": round(swap_p, 1),
        "swap_w": round(min(100.0, max(0.0, swap_p)), 1),
        "has_swap": bool(swap_total),
        "ram_label": (
            f"{human_bytes(ram_used)} / {human_bytes(ram_total)}" if online else human_bytes(ram_total)
        ),
        "disk_label": (
            f"{human_bytes(disk_used)} / {human_bytes(disk_total)}"
            if online
            else human_bytes(disk_total)
        ),
        "swap_label": (
            f"{human_bytes(swap_used)} / {human_bytes(swap_total)}"
            if online and swap_total
            else human_bytes(swap_total)
        ),
        "mem_total": human_bytes(ram_total),
        "disk_total": human_bytes(disk_total),
        "swap_total": human_bytes(swap_total),
        # 系统 / 硬件
        "os": _short(node.get("os"), 40) or "-",
        "arch": node.get("arch") or "-",
        "virt": node.get("virt") or "-",
        "gpu": _short(node.get("gpu_model"), 42),
        "gpu_pct": round(float(node.get("gpu_pct") or 0), 1),
        "agent": node.get("agent_version") or "-",
        "boot": human_time(node.get("boot_time")),
        "temp": _temp_label(node.get("temps") or []),
        # 网络 / 运行
        "net_in": human_speed(node.get("net_in_speed")) if online else "-",
        "net_out": human_speed(node.get("net_out_speed")) if online else "-",
        "traffic_down": human_bytes(node.get("net_in_total")) if online else "-",
        "traffic_up": human_bytes(node.get("net_out_total")) if online else "-",
        "load": loads,
        "procs": node.get("procs") if online else None,
        "tcp": node.get("tcp") if online else None,
        "udp": node.get("udp") if online else None,
        "uptime": human_uptime(node.get("uptime")) if online else "-",
        "ipv4": node.get("ipv4") or "",
        "ipv6": node.get("ipv6") or "",
        "remark": _short(node.get("public_note"), 60),
        # 监控
        "monitors": monitor_rows,
        "has_monitor": bool(monitor_rows),
        "delay_label": human_delay(best.get("latest")) if best else "—",
        "delay_ms": float(best.get("latest") or 0.0) if best else 0.0,
        "delay_ok": bool(best and best.get("latest_ok")),
    }


def build_summary_data(nodes: list[dict]) -> dict:
    online = sum(1 for n in nodes if n.get("online"))
    valid = [n for n in nodes if n.get("online")]
    groups: "dict[str, dict]" = {}
    total_cores = total_mem = total_disk = used_mem = used_disk = 0

    for n in nodes:
        tag = tag_of(n)
        g = groups.setdefault(
            tag,
            {"name": tag, "total": 0, "online": 0, "offline": 0, "cores": 0, "mem": 0, "disk": 0, "cpu_sum": 0.0, "cpu_n": 0},
        )
        g["total"] += 1
        if n.get("online"):
            g["online"] += 1
        else:
            g["offline"] += 1

        cores = int(n.get("cpu_cores") or 0)
        mem = int(n.get("mem_total") or 0)
        disk = int(n.get("disk_total") or 0)
        total_cores += cores
        total_mem += mem
        total_disk += disk
        g["cores"] += cores
        g["mem"] += mem
        g["disk"] += disk

        if n.get("online"):
            used_mem += int(n.get("mem_used") or 0)
            used_disk += int(n.get("disk_used") or 0)
            g["cpu_sum"] += float(n.get("cpu_pct") or 0)
            g["cpu_n"] += 1

    group_list = []
    for g in groups.values():
        total = g["total"] or 1
        g = dict(g)
        g["online_pct"] = round(g["online"] / total * 100)
        g["avg_cpu"] = round(g["cpu_sum"] / g["cpu_n"], 1) if g["cpu_n"] else 0.0
        g["cores_label"] = f"{g['cores']}核"
        g["mem_label"] = human_bytes(g["mem"])
        g["disk_label"] = human_bytes(g["disk"])
        group_list.append(g)

    n_valid = len(valid) or 1
    return {
        "total": len(nodes),
        "online": online,
        "offline": len(nodes) - online,
        "group_count": len(group_list),
        "groups": group_list,
        "avg_cpu": round(sum(float(n.get("cpu_pct") or 0) for n in valid) / n_valid, 1),
        "avg_ram": round(sum(percent(n.get("mem_used"), n.get("mem_total")) for n in valid) / n_valid, 1),
        "avg_disk": round(sum(percent(n.get("disk_used"), n.get("disk_total")) for n in valid) / n_valid, 1),
        "total_cores_label": f"{total_cores}核",
        "total_mem": human_bytes(total_mem),
        "total_disk": human_bytes(total_disk),
        "used_mem": human_bytes(used_mem),
        "used_disk": human_bytes(used_disk),
    }


def build_list_data(
    nodes: list[dict],
    monitors: Optional[dict[int, list[dict]]] = None,
    max_rows: int = 0,
    tag: str = "",
) -> dict:
    """``nodes`` 为已按 ``filter_by_tag`` 过滤后的节点；``tag`` 仅用于标题。"""
    monitors = monitors or {}
    shown = limit_rows(nodes, max_rows)
    rows = [build_node_view(n, monitors.get(n["id"])) for n in shown]
    online = sum(1 for n in nodes if n.get("online"))
    return {
        "tag": tag,
        "total": len(nodes),
        "online": online,
        "offline": len(nodes) - online,
        "rows": rows,
        "omitted": len(nodes) - len(shown),
        "show_delay": any(r["has_monitor"] for r in rows),
    }


def build_group_data(
    nodes: list[dict],
    query: str = "",
    monitors: Optional[dict[int, list[dict]]] = None,
    max_rows: int = 0,
) -> dict:
    """``nodes`` 为已按 ``filter_by_tag`` 过滤后的节点；``query`` 仅用于标题。"""
    monitors = monitors or {}
    sections = []
    for tag, items in group_by_tag(nodes).items():
        rows = [build_node_view(n, monitors.get(n["id"])) for n in limit_rows(items, max_rows)]
        on = sum(1 for n in items if n.get("online"))
        sections.append(
            {
                "name": tag,
                "total": len(items),
                "online": on,
                "offline": len(items) - on,
                "rows": rows,
            }
        )

    return {
        "title": f"分组 · {query}" if query else "服务器分组",
        "query": query,
        "sections": sections,
        "section_count": len(sections),
        "total": len(nodes),
        "show_delay": any(r["has_monitor"] for s in sections for r in s["rows"]),
    }


def visible_nodes(nodes: list[dict], max_rows: int, grouped: bool) -> list[dict]:
    """卡片 / 文本里实际会显示的节点，用于只给这些节点抓延迟监控。"""
    if not grouped:
        return limit_rows(nodes, max_rows)
    return [n for items in group_by_tag(nodes).values() for n in limit_rows(items, max_rows)]


def build_detail_data(node: dict, monitors: Optional[list[dict]] = None) -> dict:
    return {"node": build_node_view(node, monitors)}


CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
html, body {
  margin: 0; padding: 0; width: 100%;
  background: #12081a;
  color: #f8f4ff;
  font-family: "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei",
    "Noto Sans SC", sans-serif;
  -webkit-font-smoothing: antialiased;
}
.page {
  position: relative;
  width: 100%;
  overflow: hidden;
  min-height: 200px;
  transform-origin: top left;
}
.bg-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center 30%;
  z-index: 0;
  filter: brightness(0.72) saturate(1.15) contrast(1.05);
}
.bg-fallback {
  position: absolute;
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(ellipse 80% 60% at 20% 10%, rgba(244,114,182,.35), transparent 55%),
    radial-gradient(ellipse 70% 50% at 90% 20%, rgba(56,189,248,.28), transparent 50%),
    radial-gradient(ellipse 60% 50% at 50% 100%, rgba(167,139,250,.25), transparent 50%),
    linear-gradient(160deg, #1a0b24 0%, #0d1528 45%, #12081a 100%);
}
.veil {
  position: absolute;
  inset: 0;
  z-index: 1;
  background:
    linear-gradient(180deg, rgba(12,8,24,.42) 0%, rgba(12,8,24,.55) 45%, rgba(12,8,24,.72) 100%),
    radial-gradient(ellipse 90% 70% at 50% 0%, rgba(255,182,220,.12), transparent 60%);
  pointer-events: none;
}
.content {
  position: relative;
  z-index: 2;
  padding: 22px 24px 20px;
}
.glass {
  background: linear-gradient(145deg, rgba(255,255,255,.18), rgba(255,255,255,.06));
  border: 1px solid rgba(255,255,255,.28);
  box-shadow:
    0 8px 32px rgba(20, 8, 40, .35),
    inset 0 1px 0 rgba(255,255,255,.28),
    inset 0 -1px 0 rgba(255,255,255,.04);
  backdrop-filter: blur(18px) saturate(1.35);
  -webkit-backdrop-filter: blur(18px) saturate(1.35);
  border-radius: 18px;
}
.glass-soft {
  background: rgba(18, 12, 32, .38);
  border: 1px solid rgba(255,255,255,.16);
  box-shadow: 0 4px 18px rgba(10, 4, 24, .25);
  backdrop-filter: blur(14px) saturate(1.25);
  -webkit-backdrop-filter: blur(14px) saturate(1.25);
  border-radius: 14px;
}

.h {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  gap: 14px;
  padding: 14px 16px;
}
.brand .eyebrow {
  font-size: 12px;
  letter-spacing: .18em;
  text-transform: uppercase;
  color: #f9a8d4;
  font-weight: 750;
  margin-bottom: 4px;
  text-shadow: 0 0 12px rgba(249,168,212,.45);
}
.h h1 {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: -.03em;
  color: #fff;
  text-shadow: 0 2px 12px rgba(0,0,0,.35);
}
.h .sub {
  font-size: 14px;
  color: rgba(255,255,255,.72);
  margin-top: 4px;
  text-shadow: 0 1px 6px rgba(0,0,0,.3);
}
.pills { display: flex; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
.pill {
  padding: 9px 14px;
  border-radius: 14px;
  background: rgba(255,255,255,.14);
  border: 1px solid rgba(255,255,255,.26);
  text-align: center;
  min-width: 70px;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  box-shadow: inset 0 1px 0 rgba(255,255,255,.25);
}
.pill b {
  display: block;
  font-size: 21px;
  font-weight: 800;
  line-height: 1.15;
  font-variant-numeric: tabular-nums;
  color: #fff;
  text-shadow: 0 1px 8px rgba(0,0,0,.25);
}
.pill span {
  font-size: 12px;
  color: rgba(255,255,255,.7);
  margin-top: 2px;
  display: block;
}
.pill.g b { color: #86efac; text-shadow: 0 0 10px rgba(134,239,172,.4); }
.pill.r b { color: #fda4af; text-shadow: 0 0 10px rgba(253,164,175,.4); }
.pill.c b { color: #7dd3fc; text-shadow: 0 0 10px rgba(125,211,252,.45); }
.pill.p b { color: #d8b4fe; text-shadow: 0 0 10px rgba(216,180,254,.45); }
.pill.y b { color: #fde68a; text-shadow: 0 0 10px rgba(253,230,138,.4); }

.ggrid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.gcard {
  padding: 14px 16px;
  position: relative;
  overflow: hidden;
}
.gcard::before {
  content: "";
  position: absolute;
  left: 0; top: 0; bottom: 0;
  width: 3px;
  background: linear-gradient(180deg, #f9a8d4, #67e8f9);
  border-radius: 3px;
}
.gcard .n {
  font-size: 17px;
  font-weight: 760;
  margin-bottom: 8px;
  color: #fff;
  padding-left: 8px;
  text-shadow: 0 1px 8px rgba(0,0,0,.3);
}
.gcard .m {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: rgba(255,255,255,.72);
  margin-bottom: 6px;
  padding-left: 8px;
}
.gcard .avg {
  font-size: 13px;
  color: #a5f3fc;
  font-weight: 680;
  margin-bottom: 8px;
  padding-left: 8px;
  text-shadow: 0 0 8px rgba(165,243,252,.35);
}
.bar {
  height: 7px;
  border-radius: 99px;
  background: rgba(255,255,255,.14);
  overflow: hidden;
  margin-left: 8px;
  border: 1px solid rgba(255,255,255,.12);
}
.bar i {
  display: block;
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #f9a8d4, #67e8f9 55%, #c4b5fd);
  box-shadow: 0 0 10px rgba(249,168,212,.45);
}

.table-wrap { padding: 8px 12px 6px; }
table { width: 100%; border-collapse: collapse; table-layout: fixed; }
th {
  text-align: left;
  font-size: 12px;
  color: rgba(255,255,255,.62);
  font-weight: 680;
  padding: 0 6px 9px;
  border-bottom: 1px solid rgba(255,255,255,.14);
  letter-spacing: .03em;
}
td {
  padding: 9px 6px;
  font-size: 14px;
  border-bottom: 1px solid rgba(255,255,255,.07);
  vertical-align: middle;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: rgba(255,255,255,.92);
}
tr:last-child td { border-bottom: none; }
.num {
  width: 28px;
  color: rgba(255,255,255,.5);
  font-variant-numeric: tabular-nums;
  font-size: 13px;
}
.name-cell { min-width: 0; }
.name {
  font-weight: 720;
  color: #fff;
  font-size: 14px;
  text-shadow: 0 1px 6px rgba(0,0,0,.25);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.name-sub {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255,255,255,.58);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.grp { color: rgba(255,255,255,.68); font-size: 13px; }
.metric-col { text-align: right; width: 60px; }
th.metric-col { text-align: right; }
.dot {
  display: inline-block;
  width: 8px; height: 8px;
  border-radius: 50%;
  margin-right: 5px;
  vertical-align: middle;
}
.dot.on {
  background: #4ade80;
  box-shadow: 0 0 0 3px rgba(74,222,128,.22), 0 0 10px rgba(74,222,128,.55);
}
.dot.off {
  background: #fb7185;
  box-shadow: 0 0 0 3px rgba(251,113,133,.18), 0 0 10px rgba(251,113,133,.4);
}
.pct {
  font-variant-numeric: tabular-nums;
  font-weight: 740;
  color: #f1e9ff;
}
.pct.warn { color: #fcd34d; }
.pct.crit { color: #fb7185; }
.pct.good { color: #86efac; }
.off-txt { color: rgba(255,255,255,.38); }

.sec {
  margin-top: 14px;
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 0 4px;
}
.sec:first-of-type { margin-top: 2px; }
.sec h2 {
  font-size: 17px;
  font-weight: 760;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
  text-shadow: 0 1px 8px rgba(0,0,0,.3);
}
.sec h2::before {
  content: "";
  width: 4px; height: 16px;
  border-radius: 2px;
  background: linear-gradient(180deg, #f9a8d4, #67e8f9);
  display: inline-block;
  box-shadow: 0 0 8px rgba(249,168,212,.5);
}
.sec .meta { font-size: 13px; color: rgba(255,255,255,.7); }
.sec-box { padding: 6px 8px 4px; margin-bottom: 10px; }

.dhead {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
  gap: 14px;
  padding: 18px 20px;
}
.dhead h1 {
  font-size: 34px;
  font-weight: 820;
  color: #fff;
  letter-spacing: -.02em;
  text-shadow: 0 2px 14px rgba(0,0,0,.35);
}
.dhead .sub {
  margin-top: 8px;
  font-size: 21px;
  color: rgba(255,255,255,.78);
  line-height: 1.5;
  font-weight: 520;
}
.badge {
  font-size: 19px;
  font-weight: 760;
  padding: 9px 18px;
  border-radius: 999px;
  white-space: nowrap;
  flex: 0 0 auto;
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.badge.on {
  color: #bbf7d0;
  background: rgba(34,197,94,.22);
  border: 1px solid rgba(134,239,172,.45);
  box-shadow: 0 0 14px rgba(74,222,128,.25);
}
.badge.off {
  color: #fecdd3;
  background: rgba(244,63,94,.2);
  border: 1px solid rgba(251,113,133,.4);
}
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
.tag {
  font-size: 17px;
  padding: 5px 13px;
  border-radius: 999px;
  background: rgba(249,168,212,.18);
  color: #fbcfe8;
  border: 1px solid rgba(249,168,212,.35);
  font-weight: 600;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
.metric {
  padding: 18px 18px 16px;
  min-height: 124px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.metric .l {
  font-size: 21px;
  color: rgba(255,255,255,.78);
  margin-bottom: 8px;
  font-weight: 680;
  letter-spacing: .04em;
}
.metric .v {
  font-size: 40px;
  font-weight: 860;
  font-variant-numeric: tabular-nums;
  line-height: 1.0;
  text-shadow: 0 0 20px currentColor;
  letter-spacing: -.02em;
}
.metric .h {
  margin-top: 10px;
  font-size: 20px;
  color: rgba(255,255,255,.72);
  line-height: 1.4;
  font-weight: 550;
}
.section-title {
  font-size: 20px;
  font-weight: 760;
  color: #f9a8d4;
  letter-spacing: .1em;
  text-transform: uppercase;
  margin: 6px 2px 12px;
  text-shadow: 0 0 10px rgba(249,168,212,.35);
}
.panel { padding: 16px 18px; margin-bottom: 14px; }
.rows { display: flex; flex-direction: column; gap: 12px; }
.row {
  display: grid;
  grid-template-columns: 58px 1fr 74px;
  gap: 12px;
  align-items: center;
  font-size: 21px;
}
.row .k { color: rgba(255,255,255,.75); font-weight: 680; }
.row .v {
  text-align: right;
  font-weight: 760;
  font-variant-numeric: tabular-nums;
  color: #fff;
  font-size: 21px;
}
.track {
  height: 11px;
  border-radius: 99px;
  background: rgba(255,255,255,.14);
  overflow: hidden;
  border: 1px solid rgba(255,255,255,.1);
}
.fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, #f9a8d4, #67e8f9 60%, #c4b5fd);
  box-shadow: 0 0 12px rgba(249,168,212,.4);
}
.fill.warn { background: linear-gradient(90deg, #fbbf24, #fb923c); box-shadow: 0 0 10px rgba(251,191,36,.4); }
.fill.crit { background: linear-gradient(90deg, #fb7185, #f43f5e); box-shadow: 0 0 10px rgba(251,113,133,.45); }
.kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 9px;
}
.kv .item {
  border-radius: 12px;
  padding: 13px 15px;
  background: rgba(255,255,255,.1);
  border: 1px solid rgba(255,255,255,.16);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}
.kv .item .k {
  font-size: 18px;
  color: rgba(255,255,255,.68);
  margin-bottom: 5px;
  font-weight: 650;
}
.kv .item .v {
  font-size: 20px;
  font-weight: 700;
  color: #fff;
  word-break: break-all;
  line-height: 1.4;
  text-shadow: 0 1px 6px rgba(0,0,0,.2);
}
.kv .item .v.bad { color: #fda4af; }
.kv .item .v.good { color: #86efac; }
.empty {
  text-align: center;
  padding: 32px 12px;
  color: rgba(255,255,255,.7);
  font-size: 15px;
}
.foot {
  margin-top: 2px;
  text-align: right;
  font-size: 12px;
  color: rgba(255,255,255,.5);
}
"""


# AstrBot 自 v4.23 起给 t2i 模板加入 Shiki 代码高亮（4.27.4 源码中的 NetworkRenderStrategy
# 会往每个自定义模板 </head> 前注入 ~1.2 MB 运行时），除非模板里已含 id "astrbot-t2i-shiki-runtime"。卡片不含代码块，
# 用注释占位跳过注入：实测约 50 节点列表 POST 体 1529 KiB → 71 KiB，本地 Chromium 渲染快约 200 ms。
# 旧版 AstrBot 不认这个标记，只是一段无害注释。
SHIKI_OPT_OUT = "<!-- astrbot-t2i-shiki-runtime: not needed -->"


def _doc(width: int, body: str) -> str:
    """玻璃卡片骨架：随机二次元底图 + 毛玻璃内容层。"""
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
{SHIKI_OPT_OUT}
<meta name="viewport" content="width={width}, height=480">
<style>
{CSS}
html, body {{ width: {width}px; max-width: {width}px; }}
.page {{ width: {width}px; max-width: {width}px; }}
</style>
</head>
<body>
<div class="page">
  <div class="bg-fallback"></div>
  <img class="bg-img" src="{{{{ bg_url }}}}" alt="" />
  <div class="veil"></div>
  <div class="content">
{body}
  </div>
</div>
</body>
</html>"""


TMPL_SUMMARY = _doc(
    WIDTH_SUMMARY,
    """
  <div class="h glass" style="flex-direction:column;align-items:stretch;gap:12px;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
      <div class="brand">
        <div class="eyebrow">Nezha · Server</div>
        <h1>服务器概况</h1>
        <div class="sub">{{ group_count }} 个分组 · {{ total }} 台节点 · 在线均 CPU {{ avg_cpu }}% / 内存 {{ avg_ram }}% / 磁盘 {{ avg_disk }}%</div>
      </div>
      <div class="pills">
        <div class="pill"><b>{{ total }}</b><span>总计</span></div>
        <div class="pill g"><b>{{ online }}</b><span>在线</span></div>
        <div class="pill r"><b>{{ offline }}</b><span>离线</span></div>
      </div>
    </div>
    <div class="pills" style="justify-content:flex-start;">
      <div class="pill c"><b>{{ total_cores_label }}</b><span>CPU 总数</span></div>
      <div class="pill p"><b>{{ total_mem }}</b><span>内存总数</span></div>
      <div class="pill y"><b>{{ total_disk }}</b><span>硬盘总数</span></div>
      <div class="pill"><b>{{ used_mem }}</b><span>内存已用</span></div>
      <div class="pill"><b>{{ used_disk }}</b><span>硬盘已用</span></div>
    </div>
  </div>
  {% if groups %}
  <div class="ggrid">
    {% for g in groups %}
    <div class="gcard glass-soft">
      <div class="n">{{ g.name }}</div>
      <div class="m">
        <span>在线 {{ g.online }}/{{ g.total }}</span>
        <span>离线 {{ g.offline }}</span>
      </div>
      <div class="avg">{{ g.cores_label }} · 内存 {{ g.mem_label }} · 盘 {{ g.disk_label }} · 均CPU {{ g.avg_cpu }}%</div>
      <div class="bar"><i style="width:{{ g.online_pct }}%"></i></div>
    </div>
    {% endfor %}
  </div>
  {% else %}
  <div class="empty glass-soft">暂无服务器</div>
  {% endif %}
""",
)


TMPL_LIST = _doc(
    WIDTH_LIST,
    """
  <div class="h glass">
    <div class="brand">
      <div class="eyebrow">Nezha · Server</div>
      <h1>服务器列表{% if tag %} · {{ tag }}{% endif %}</h1>
      <div class="sub">共 {{ total }} 台{% if omitted %} · 仅显示前 {{ rows | length }} 台{% endif %} · 序号可直接用于 /nz &lt;序号&gt;</div>
    </div>
    <div class="pills">
      <div class="pill g"><b>{{ online }}</b><span>在线</span></div>
      <div class="pill r"><b>{{ offline }}</b><span>离线</span></div>
    </div>
  </div>
  {% if rows %}
  <div class="table-wrap glass-soft">
  <table>
    <colgroup>
      <col style="width:28px">
      <col style="width:34%">
      <col style="width:58px">
      <col style="width:54px">
      <col style="width:54px">
      <col style="width:54px">
      <col style="width:74px">
      {% if show_delay %}<col style="width:74px">{% endif %}
    </colgroup>
    <thead>
      <tr>
        <th class="num">#</th>
        <th>名称 / 分组</th>
        <th>状态</th>
        <th class="metric-col">负载</th>
        <th class="metric-col">内存</th>
        <th class="metric-col">磁盘</th>
        <th class="metric-col">网速↓</th>
        {% if show_delay %}<th class="metric-col">延迟</th>{% endif %}
      </tr>
    </thead>
    <tbody>
    {% for r in rows %}
      <tr>
        <td class="num">{{ r.index }}</td>
        <td class="name-cell">
          <div class="name">{{ r.flag }} {{ r.name }}</div>
          <div class="name-sub">{{ r.tag }}{% if r.hidden %} · 隐藏{% endif %}</div>
        </td>
        <td>{% if r.online %}<span class="dot on"></span>在线{% else %}<span class="dot off"></span>离线{% endif %}</td>
        {% if r.online %}
        <td class="pct metric-col {% if r.cpu >= 90 %}crit{% elif r.cpu >= 70 %}warn{% endif %}">{{ r.cpu }}%</td>
        <td class="pct metric-col {% if r.ram_p >= 90 %}crit{% elif r.ram_p >= 75 %}warn{% endif %}">{{ r.ram_p }}%</td>
        <td class="pct metric-col {% if r.disk_p >= 90 %}crit{% elif r.disk_p >= 80 %}warn{% endif %}">{{ r.disk_p }}%</td>
        <td class="grp metric-col">{{ r.net_in }}</td>
        {% else %}
        <td class="off-txt metric-col">—</td>
        <td class="off-txt metric-col">—</td>
        <td class="off-txt metric-col">—</td>
        <td class="off-txt metric-col">—</td>
        {% endif %}
        {% if show_delay %}
        <td class="metric-col {% if not r.online or not r.has_monitor %}off-txt{% elif not r.delay_ok %}pct crit{% elif r.delay_ms < 100 %}pct good{% elif r.delay_ms < 300 %}pct{% else %}pct warn{% endif %}">{{ r.delay_label }}</td>
        {% endif %}
      </tr>
    {% endfor %}
    </tbody>
  </table>
  </div>
  {% else %}
  <div class="empty glass-soft">暂无服务器</div>
  {% endif %}
""",
)


TMPL_DETAIL = _doc(
    WIDTH_DETAIL,
    """
  <div class="dhead glass">
    <div>
      <div class="eyebrow" style="font-size:18px;letter-spacing:.18em;text-transform:uppercase;color:#f9a8d4;font-weight:750;margin-bottom:5px;text-shadow:0 0 12px rgba(249,168,212,.45);">Nezha · Node</div>
      <h1>{{ node.flag }} {{ node.name }}</h1>
      <div class="sub">{{ node.tag }} · {{ node.os }} · {{ node.arch }}{% if node.virt != '-' %} / {{ node.virt }}{% endif %}</div>
      <div class="tags">
        <span class="tag">ID {{ node.id }}</span>
        <span class="tag">{{ node.cores_label }}</span>
        {% if node.ipv4 %}<span class="tag">{{ node.ipv4 }}</span>{% endif %}
        {% if node.ipv6 %}<span class="tag">{{ node.ipv6 }}</span>{% endif %}
      </div>
    </div>
    {% if node.online %}
    <span class="badge on">在线</span>
    {% else %}
    <span class="badge off">离线</span>
    {% endif %}
  </div>

  {% if node.online %}
  <div class="metrics">
    <div class="metric glass-soft">
      <div class="l">CPU 使用率</div>
      <div class="v" style="color:#7dd3fc">{{ node.cpu }}%</div>
      <div class="h">{{ node.cores_label }}</div>
    </div>
    <div class="metric glass-soft">
      <div class="l">内存</div>
      <div class="v" style="color:#d8b4fe">{{ node.ram_p }}%</div>
      <div class="h">{{ node.ram_label }}</div>
    </div>
    <div class="metric glass-soft">
      <div class="l">磁盘</div>
      <div class="v" style="color:#86efac">{{ node.disk_p }}%</div>
      <div class="h">{{ node.disk_label }}</div>
    </div>
  </div>

  <div class="panel glass-soft">
    <div class="section-title">负载</div>
    <div class="rows">
      <div class="row">
        <div class="k">CPU</div>
        <div class="track"><div class="fill {% if node.cpu >= 90 %}crit{% elif node.cpu >= 70 %}warn{% endif %}" style="width:{{ node.cpu_w }}%"></div></div>
        <div class="v">{{ node.cpu }}%</div>
      </div>
      <div class="row">
        <div class="k">内存</div>
        <div class="track"><div class="fill {% if node.ram_p >= 90 %}crit{% elif node.ram_p >= 75 %}warn{% endif %}" style="width:{{ node.ram_w }}%"></div></div>
        <div class="v">{{ node.ram_p }}%</div>
      </div>
      <div class="row">
        <div class="k">磁盘</div>
        <div class="track"><div class="fill {% if node.disk_p >= 90 %}crit{% elif node.disk_p >= 80 %}warn{% endif %}" style="width:{{ node.disk_w }}%"></div></div>
        <div class="v">{{ node.disk_p }}%</div>
      </div>
      {% if node.has_swap %}
      <div class="row">
        <div class="k">交换</div>
        <div class="track"><div class="fill {% if node.swap_p >= 80 %}warn{% endif %}" style="width:{{ node.swap_w }}%"></div></div>
        <div class="v">{{ node.swap_p }}%</div>
      </div>
      {% endif %}
    </div>
  </div>

  <div class="panel glass-soft">
    <div class="section-title">网络 · 运行</div>
    <div class="kv">
      <div class="item"><div class="k">实时网速（↓ 入 / ↑ 出）</div><div class="v">↓ {{ node.net_in }} · ↑ {{ node.net_out }}</div></div>
      <div class="item"><div class="k">累计流量（↓ 入 / ↑ 出）</div><div class="v">↓ {{ node.traffic_down }} · ↑ {{ node.traffic_up }}</div></div>
      <div class="item"><div class="k">进程 / 连接</div><div class="v">{{ node.procs }} 进程 · TCP {{ node.tcp }} / UDP {{ node.udp }}</div></div>
      <div class="item"><div class="k">运行时间</div><div class="v">{{ node.uptime }}</div></div>
      {% if node.has_swap %}
      <div class="item"><div class="k">交换分区</div><div class="v">{{ node.swap_label }}</div></div>
      {% endif %}
      <div class="item"><div class="k">最后上报</div><div class="v">{{ node.last_active }}</div></div>
      {% if node.gpu %}
      <div class="item"><div class="k">GPU</div><div class="v">{{ node.gpu }} · {{ node.gpu_pct }}%</div></div>
      {% endif %}
      {% if node.temp %}
      <div class="item"><div class="k">温度</div><div class="v">{{ node.temp }}</div></div>
      {% endif %}
    </div>
  </div>

  <div class="panel glass-soft">
    <div class="section-title">硬件 · 系统</div>
    <div class="kv">
      <div class="item"><div class="k">CPU 型号</div><div class="v">{{ node.cpu_name }}</div></div>
      <div class="item"><div class="k">核心</div><div class="v">{{ node.cores_label }} · {{ node.arch }}</div></div>
      <div class="item"><div class="k">虚拟化</div><div class="v">{{ node.virt }}</div></div>
      <div class="item"><div class="k">系统负载 1/5/15</div><div class="v">{{ node.load }}</div></div>
      <div class="item"><div class="k">内存 / 磁盘</div><div class="v">{{ node.mem_total }} / {{ node.disk_total }}</div></div>
      <div class="item"><div class="k">系统 / Agent</div><div class="v">{{ node.os }} · {{ node.agent }}</div></div>
    </div>
  </div>

  {% if node.has_monitor %}
  <div class="panel glass-soft">
    <div class="section-title">网络质量监控</div>
    <div class="kv">
      {% for m in node.monitors %}
      <div class="item">
        <div class="k">{{ m.name }}（最近 {{ m.points }} 次）</div>
        <div class="v {% if not m.latest_ok %}bad{% elif m.loss_bad %}bad{% else %}good{% endif %}">
          延迟 {{ m.latest }} · 丢包 {{ m.loss_pct }}%
        </div>
        <div class="k" style="margin-top:6px;margin-bottom:0;">平均 {{ m.avg }} · 最好 {{ m.best }} · 最差 {{ m.worst }}</div>
      </div>
      {% endfor %}
    </div>
  </div>
  {% endif %}

  {% if node.remark %}
  <div class="panel glass-soft">
    <div class="section-title">备注</div>
    <div class="rows"><div class="row" style="grid-template-columns:1fr;"><div class="v" style="text-align:left;font-weight:600;">{{ node.remark }}</div></div></div>
  </div>
  {% endif %}

  {% else %}
  <div class="panel glass-soft">
    <div class="kv" style="margin-bottom:8px;">
      <div class="item"><div class="k">CPU</div><div class="v">{{ node.cpu_label }}</div></div>
      <div class="item"><div class="k">规格</div><div class="v">内存 {{ node.mem_total }} · 磁盘 {{ node.disk_total }}</div></div>
      <div class="item"><div class="k">系统</div><div class="v">{{ node.os }}</div></div>
      <div class="item"><div class="k">架构 / 虚拟化</div><div class="v">{{ node.arch }}{% if node.virt != '-' %} / {{ node.virt }}{% endif %}</div></div>
      <div class="item"><div class="k">上次在线</div><div class="v">{{ node.last_active }}</div></div>
      {% if node.ipv4 %}
      <div class="item"><div class="k">IPv4</div><div class="v">{{ node.ipv4 }}</div></div>
      {% endif %}
    </div>
    <div class="empty">该服务器当前离线，暂无实时负载</div>
  </div>
  {% endif %}

  <div class="foot">数据来源：{{ base_url }} · {{ fetched_at }}</div>
""",
)


TMPL_GROUP = _doc(
    WIDTH_GROUP,
    """
  <div class="h glass">
    <div class="brand">
      <div class="eyebrow">Nezha · Server</div>
      <h1>{{ title }}</h1>
      <div class="sub">{{ section_count }} 个分组 · {{ total }} 台</div>
    </div>
  </div>
  {% if sections %}
    {% for s in sections %}
    <div class="sec">
      <h2>{{ s.name }}</h2>
      <div class="meta">在线 {{ s.online }}/{{ s.total }}{% if s.offline %} · 离线 {{ s.offline }}{% endif %}</div>
    </div>
    <div class="sec-box glass-soft">
      <table>
        <colgroup>
          <col style="width:28px">
          <col style="width:44%">
          <col style="width:58px">
          <col style="width:54px">
          <col style="width:54px">
          <col style="width:54px">
          {% if show_delay %}<col style="width:74px">{% endif %}
        </colgroup>
        <thead>
          <tr>
            <th class="num">#</th>
            <th>名称</th>
            <th>状态</th>
            <th class="metric-col">负载</th>
            <th class="metric-col">内存</th>
            <th class="metric-col">磁盘</th>
            {% if show_delay %}<th class="metric-col">延迟</th>{% endif %}
          </tr>
        </thead>
        <tbody>
        {% for r in s.rows %}
          <tr>
            <td class="num">{{ r.index }}</td>
            <td class="name-cell"><div class="name">{{ r.flag }} {{ r.name }}</div></td>
            <td>{% if r.online %}<span class="dot on"></span>在线{% else %}<span class="dot off"></span>离线{% endif %}</td>
            {% if r.online %}
            <td class="pct metric-col {% if r.cpu >= 90 %}crit{% elif r.cpu >= 70 %}warn{% endif %}">{{ r.cpu }}%</td>
            <td class="pct metric-col {% if r.ram_p >= 90 %}crit{% elif r.ram_p >= 75 %}warn{% endif %}">{{ r.ram_p }}%</td>
            <td class="pct metric-col {% if r.disk_p >= 90 %}crit{% elif r.disk_p >= 80 %}warn{% endif %}">{{ r.disk_p }}%</td>
            {% else %}
            <td class="off-txt metric-col">—</td>
            <td class="off-txt metric-col">—</td>
            <td class="off-txt metric-col">—</td>
            {% endif %}
            {% if show_delay %}
            <td class="metric-col {% if not r.online or not r.has_monitor %}off-txt{% elif not r.delay_ok %}pct crit{% elif r.delay_ms < 100 %}pct good{% elif r.delay_ms < 300 %}pct{% else %}pct warn{% endif %}">{{ r.delay_label }}</td>
            {% endif %}
          </tr>
        {% endfor %}
        </tbody>
      </table>
    </div>
    {% endfor %}
  {% else %}
  <div class="empty glass-soft">未找到分组</div>
  {% endif %}
""",
)
