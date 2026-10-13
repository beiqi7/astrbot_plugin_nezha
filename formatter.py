"""纯文本渲染与通用格式化工具（卡片模板同样复用这里的辅助函数）。"""

from __future__ import annotations

import time
from typing import Any, Optional

# 地区旗帜：由两位 CountryCode 计算区域指示符（不硬编码任何旗帜字符）
_FLAG_BASE = 0x1F1E6
# 特殊映射：tw 统一按 cn 展示
_ALIAS_FLAGS = {"tw": "cn", "uk": "gb", "el": "gr"}

DOT_ON = "\U0001f7e2"
DOT_OFF = "\U0001f534"
ICON_SUMMARY = "\U0001f4ca"
ICON_LIST = "\U0001f4cb"
ICON_GROUP = "\U0001f5c2\ufe0f"
ICON_NODE = "\U0001f5a5\ufe0f"
ICON_NET = "\U0001f4e1"
ICON_DENY = "\u26d4"
ICON_WARN = "\u26a0\ufe0f"
ICON_FAIL = "\u274c"
ICON_OK = "\u2705"
ARROW_DOWN = "\u2193"
ARROW_UP = "\u2191"


def flag_emoji(code: str) -> str:
    """把两位国家代码转成旗帜；无法识别时返回空字符串。"""
    code = str(code or "").strip().lower()
    code = _ALIAS_FLAGS.get(code, code)
    if len(code) != 2 or not code.isalpha() or not code.isascii():
        return ""
    return "".join(chr(_FLAG_BASE + ord(ch) - 97) for ch in code)


def human_bytes(n: Any) -> str:
    try:
        num = float(n or 0)
    except (TypeError, ValueError):
        return "0 B"
    if num < 0:
        num = 0
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    i = 0
    while num >= 1024 and i < len(units) - 1:
        num /= 1024
        i += 1
    if i == 0:
        return f"{int(num)} {units[i]}"
    return f"{num:.2f} {units[i]}"


def human_speed(n: Any) -> str:
    return f"{human_bytes(n)}/s"


def percent(used: Any, total: Any) -> float:
    try:
        u = float(used or 0)
        t = float(total or 0)
    except (TypeError, ValueError):
        return 0.0
    if t <= 0:
        return 0.0
    return max(0.0, min(100.0, u / t * 100))


def human_uptime(seconds: Any) -> str:
    try:
        s = int(float(seconds or 0))
    except (TypeError, ValueError):
        return "-"
    if s <= 0:
        return "-"
    days, rem = divmod(s, 86400)
    hours, rem = divmod(rem, 3600)
    mins, _ = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}天")
    if hours or days:
        parts.append(f"{hours}时")
    parts.append(f"{mins}分")
    return "".join(parts)


def human_age(seconds: Any) -> str:
    """距上次上报的时长，用于判断节点新鲜度。"""
    try:
        s = int(float(seconds or 0))
    except (TypeError, ValueError):
        return "-"
    if s < 60:
        return f"{s} 秒前"
    if s < 3600:
        return f"{s // 60} 分钟前"
    if s < 86400:
        return f"{s // 3600} 小时前"
    return f"{s // 86400} 天前"


def human_time(ts: Any) -> str:
    try:
        t = int(float(ts or 0))
    except (TypeError, ValueError):
        return "-"
    if t <= 0:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(t))


def human_delay(ms: Any) -> str:
    """延迟：0 视为超时。"""
    try:
        v = float(ms or 0)
    except (TypeError, ValueError):
        return "超时"
    if v <= 0:
        return "超时"
    if v < 1000:
        return f"{v:.1f}ms"
    return f"{v / 1000:.2f}s"


def cpu_label(node: dict) -> str:
    name = str(node.get("cpu_name") or "").strip() or "-"
    cores = node.get("cpu_cores")
    if cores:
        return f"{name} x {cores}"
    return name


def cores_label(node: dict) -> str:
    cores = node.get("cpu_cores")
    if not cores:
        return "-"
    kind = str(node.get("cpu_kind") or "")
    suffix = "核"
    if kind == "Physical":
        suffix = "物理核"
    elif kind == "Virtual":
        suffix = "虚拟核"
    return f"{cores} {suffix}"


def format_help(prefix: str = "nz") -> str:
    p = prefix
    return (
        f"{ICON_NET} 哪吒服务器监控\n"
        "──────────────\n"
        f"/{p}              服务器概况\n"
        f"/{p} list [分组]  服务器列表\n"
        f"/{p} group [分组] 按分组查看\n"
        f"/{p} <名称|ID|序号> 单机详情（含延迟监控）\n"
        f"/{p} help         查看帮助\n"
        f"/{p} sid          查看自己的用户 ID\n"
        "──────────────\n"
        "名称支持模糊匹配：节点名 / 分组 / ID / 列表序号 / IP\n"
        f"示例：/{p} list  |  /{p} DMIT  |  /{p} group AWS  |  /{p} 6"
    )


def format_summary(nodes: list[dict]) -> str:
    if not nodes:
        return "面板没有返回任何服务器。"
    online = sum(1 for n in nodes if n.get("online"))
    total_cores = sum(int(n.get("cpu_cores") or 0) for n in nodes)
    total_mem = sum(int(n.get("mem_total") or 0) for n in nodes)
    total_disk = sum(int(n.get("disk_total") or 0) for n in nodes)
    used_mem = sum(int(n.get("mem_used") or 0) for n in nodes if n.get("online"))
    used_disk = sum(int(n.get("disk_used") or 0) for n in nodes if n.get("online"))
    valid = [n for n in nodes if n.get("online")]
    avg_cpu = sum(float(n.get("cpu_pct") or 0) for n in valid) / len(valid) if valid else 0.0
    avg_ram = (
        sum(percent(n.get("mem_used"), n.get("mem_total")) for n in valid) / len(valid)
        if valid
        else 0.0
    )
    avg_disk = (
        sum(percent(n.get("disk_used"), n.get("disk_total")) for n in valid) / len(valid)
        if valid
        else 0.0
    )

    lines = [
        f"{ICON_SUMMARY} 服务器概况",
        "──────────────",
        f"总计 {len(nodes)} · 在线 {online} · 离线 {len(nodes) - online}",
        f"CPU 总数 {total_cores} 核",
        f"内存总数 {human_bytes(total_mem)}（已用 {human_bytes(used_mem)}）",
        f"硬盘总数 {human_bytes(total_disk)}（已用 {human_bytes(used_disk)}）",
        f"在线均 CPU {avg_cpu:.1f}% · 内存 {avg_ram:.1f}% · 磁盘 {avg_disk:.1f}%",
        "──────────────",
    ]
    for tag, items in group_by_tag(nodes).items():
        on = sum(1 for n in items if n.get("online"))
        cores = sum(int(n.get("cpu_cores") or 0) for n in items)
        mem = sum(int(n.get("mem_total") or 0) for n in items)
        lines.append(
            f"· {tag}：{on}/{len(items)} 在线 · {cores} 核 · {human_bytes(mem)}"
        )
    return "\n".join(lines)


UNGROUPED = "未分组"


def tag_of(node: dict) -> str:
    return str(node.get("tag") or "").strip() or UNGROUPED


def group_by_tag(nodes: list[dict]) -> "dict[str, list[dict]]":
    """按分组分桶，保持面板顺序（分组按首次出现排序）。"""
    buckets: "dict[str, list[dict]]" = {}
    for n in nodes:
        buckets.setdefault(tag_of(n), []).append(n)
    return buckets


def filter_by_tag(nodes: list[dict], query: str) -> list[dict]:
    """按分组过滤：先精确匹配（忽略大小写），没有再子串匹配；空查询返回全部。"""
    q = (query or "").strip().lower()
    if not q:
        return nodes
    exact = [n for n in nodes if tag_of(n).lower() == q]
    return exact or [n for n in nodes if q in tag_of(n).lower()]


def limit_rows(items: list, max_rows: int) -> list:
    """``max_rows <= 0`` 表示不限制。"""
    return items[:max_rows] if max_rows and max_rows > 0 else items


def format_list(nodes: list[dict], max_rows: int = 0, tag: str = "") -> str:
    if not nodes:
        return "面板没有返回任何服务器。"
    online = sum(1 for n in nodes if n.get("online"))
    shown = limit_rows(nodes, max_rows)
    title = f"服务器列表 · {tag}" if tag else "服务器列表"
    lines = [
        f"{ICON_LIST} {title}（共 {len(nodes)} · 在线 {online}）",
        "──────────────",
    ]
    lines.extend(_node_line(n) for n in shown)
    if len(shown) < len(nodes):
        lines.append(f"… 其余 {len(nodes) - len(shown)} 台已省略（可调大 max_list_rows）")
    return "\n".join(lines)


def _node_line(n: dict) -> str:
    """单行节点摘要；行首是全局序号，可直接用于 ``/nz <序号>``。"""
    index = n.get("index", 0)
    flag = flag_emoji(n.get("country"))
    name = f"{flag} {n.get('name') or '?'}".strip()
    tag = str(n.get("tag") or "").strip()
    extra = f" [{tag}]" if tag else ""
    if not n.get("online"):
        return f"{index}. {DOT_OFF} {name}{extra}  离线 · {human_age(n.get('age'))}"
    return (
        f"{index}. {DOT_ON} {name}{extra}  "
        f"CPU {float(n.get('cpu_pct') or 0):.1f}% · "
        f"内存 {percent(n.get('mem_used'), n.get('mem_total')):.0f}% · "
        f"磁盘 {percent(n.get('disk_used'), n.get('disk_total')):.0f}% · "
        f"{ARROW_DOWN}{human_speed(n.get('net_in_speed'))}"
    )


def format_node(node: dict, monitors: Optional[list[dict]] = None) -> str:
    flag = flag_emoji(node.get("country"))
    title = f"{flag} {node.get('name') or '未命名'}".strip()
    tag = str(node.get("tag") or "").strip() or "未分组"
    lines = [
        f"{ICON_NODE} {title}",
        f"ID {node.get('id')} · 分组 {tag}",
        f"状态：{DOT_ON + ' 在线' if node.get('online') else DOT_OFF + ' 离线'}"
        f"（{human_age(node.get('age'))}上报）",
        f"CPU：{cpu_label(node)}",
        f"系统：{node.get('os') or '-'} · {node.get('arch') or '-'}"
        + (f" · {node.get('virt')}" if node.get("virt") else ""),
        f"规格：内存 {human_bytes(node.get('mem_total'))} · 磁盘 {human_bytes(node.get('disk_total'))}"
        + (f" · 交换 {human_bytes(node.get('swap_total'))}" if node.get("swap_total") else ""),
    ]
    if node.get("ipv4"):
        lines.append(f"IPv4：{node['ipv4']}")
    if node.get("ipv6"):
        lines.append(f"IPv6：{node['ipv6']}")

    if node.get("online"):
        cpu = float(node.get("cpu_pct") or 0)
        ram_p = percent(node.get("mem_used"), node.get("mem_total"))
        disk_p = percent(node.get("disk_used"), node.get("disk_total"))
        loads = f"{node.get('load1', 0):.2f} / {node.get('load5', 0):.2f} / {node.get('load15', 0):.2f}"
        lines.extend(
            [
                "──────────────",
                f"负载 CPU {cpu:.1f}% · 内存 {ram_p:.1f}% · 磁盘 {disk_p:.1f}%",
                f"内存 {human_bytes(node.get('mem_used'))} / {human_bytes(node.get('mem_total'))}",
                f"磁盘 {human_bytes(node.get('disk_used'))} / {human_bytes(node.get('disk_total'))}",
                f"网速 {ARROW_DOWN}{human_speed(node.get('net_in_speed'))} "
                f"{ARROW_UP}{human_speed(node.get('net_out_speed'))}",
                f"流量 {ARROW_DOWN}{human_bytes(node.get('net_in_total'))} "
                f"{ARROW_UP}{human_bytes(node.get('net_out_total'))}",
                f"系统负载 {loads} · 进程 {node.get('procs')} · "
                f"TCP {node.get('tcp')} / UDP {node.get('udp')}",
                f"运行 {human_uptime(node.get('uptime'))} · 开机于 {human_time(node.get('boot_time'))}",
            ]
        )
        temps = node.get("temps") or []
        if temps:
            lines.append("温度 " + " · ".join(f"{t['name']} {t['value']:.0f}°C" for t in temps))
        if node.get("gpu_model"):
            lines.append(f"GPU {node['gpu_model']}（{float(node.get('gpu_pct') or 0):.0f}%）")
    else:
        lines.append("──────────────")
        lines.append("离线，暂无实时负载")

    if monitors:
        lines.append("──────────────")
        lines.append(f"{ICON_NET} 网络质量监控（最近 {monitors[0].get('points')} 次探测）")
        for m in monitors:
            lines.append(
                f"· {m['name']}：{human_delay(m['latest'])} · "
                f"丢包 {m['loss_pct']:.1f}% · 平均 {human_delay(m['avg'])}"
                + (f" · 最好 {human_delay(m['best'])}" if m.get("best") else "")
            )
    elif node.get("online"):
        lines.append("（该服务器未配置监控）")

    if node.get("agent_version"):
        lines.append(f"Agent {node['agent_version']}")
    if node.get("public_note"):
        lines.append(f"备注：{node['public_note']}")
    return "\n".join(lines)


def format_group(nodes: list[dict], query: str = "", max_rows: int = 0) -> str:
    """``nodes`` 为已按 ``filter_by_tag`` 过滤后的节点；``query`` 仅用于标题。"""
    if not nodes:
        return f"未找到分组「{query}」。" if query else "面板没有返回任何服务器。"
    lines = [f"{ICON_GROUP} 服务器分组" + (f" · {query}" if query else ""), "──────────────"]
    for tag, items in group_by_tag(nodes).items():
        on = sum(1 for n in items if n.get("online"))
        lines.append(f"【{tag}】{on}/{len(items)} 在线")
        lines.extend("  " + _node_line(n) for n in limit_rows(items, max_rows))
        lines.append("")
    return "\n".join(lines).rstrip()
