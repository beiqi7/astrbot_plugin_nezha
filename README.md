# 哪吒探针（Nezha v0 魔改版）· AstrBot 插件

在 AstrBot / NapCat（OneBot v11）里查看哪吒面板的服务器信息：概况、列表、分组、单机详情，
卡片为二次元玻璃拟态高清图片，渲染失败会自动回退成纯文本。

> 面向的是**哪吒 v0 时期的老接口**（`nezha-zero` 系魔改版），
> 不是哪吒官方 v1 的 REST / gRPC 结构。

## 安装

1. 把 `astrbot_plugin_nezha` 整个目录放进 AstrBot 的 `data/plugins/` 下（或从仓库安装）。
2. 依赖只有 `aiohttp`，AstrBot 自带，无需额外安装。
3. 重启 / 重载插件，到 **AstrBot 后台 → 插件 → 哪吒探针** 填 `base_url` 与 `api_token`（两者必填）。

## 配置

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `base_url` | 空（**必填**） | 面板根地址，**不要**带 `/api` 或 `/api/v1`（带了也会自动去掉） |
| `api_token` | 空（**必填**） | 面板「API Token」签发，请求头 `Authorization` 直传 |
| `timeout` | `10` | 单次请求超时（秒） |
| `online_threshold` | `20` | 在线判定：距上次上报 ≤ N 秒（官方主题就是 20 秒） |
| `show_hidden` | `true` | 是否显示「游客不可见」的隐藏节点 |
| `output_mode` | `card` | `card` 图片卡片 / `text` 纯文本 |
| `image_quality` | `high` | `normal` 960px 宽 · `high` 1248px · `ultra` 1728px（走文转图服务的 `device_scale_factor_level`，真实提升渲染分辨率；约 50 节点列表实测 0.57/1.63/3.04 MB） |
| `enable_monitor` | `true` | 单机详情展示魔改版的延迟 / 丢包监控 |
| `monitor_in_list` | `false` | 列表 / 分组卡片加一列延迟（只为实际显示的在线行各发一次请求，节点多时较慢） |
| `monitor_points` | `60` | 延迟统计取最近多少次探测 |
| `max_list_rows` | `60` | 列表最多显示多少台，`0` 不限；超出部分在卡片与文本中都会省略 |
| `permission_mode` | `all` | `all` / `admin` / `whitelist`（管理员始终可用） |
| `allowed_users` | 空 | 白名单用户 ID，逗号或换行分隔 |
| `bg_url` | `https://mygo.pp.ua/` | 卡片背景随机图接口 |

> ⚠️ `base_url` 与 `api_token` 默认为空，不填会直接提示未配置。
> Token 能读取面板全部节点数据，请只填在 AstrBot 后台的插件配置里，不要提交进仓库或日志。

## 指令

| 指令 | 说明 |
| --- | --- |
| `/nz` | 服务器概况（总/在线/离线、总核数、总内存磁盘、分组聚合） |
| `/nz list [分组]` | 服务器列表（状态、负载、内存、磁盘、网速，可选延迟列） |
| `/nz group [分组]` | 按面板分组（`tag`）分节查看 |
| `/nz <名称\|ID\|序号>` | 单机详情：CPU/内存/磁盘/交换、系统负载、温度、GPU、网速与累计流量、进程与连接数、运行时间、延迟与丢包 |
| `/nz info <名称>` | 同上，显式写法 |
| `/nz help` | 帮助 |
| `/nz sid` | 查看自己的用户 ID（配白名单用） |

别名：`/nezha`、`/哪吒`、`/探针`。
名称支持模糊匹配：节点名 / 分组 / ID / 列表序号 / IP，最高分并列时（例如「序号 1」和「ID 1」是两台机器）会先列出候选让你写具体。

* **序号是全局的**：列表 / 分组卡片和文本里 `#` 列就是面板顺序下的全局编号，按分组过滤后也不变，
  看到几号就能直接 `/nz <序号>`。
* **分组过滤**：`list` 与 `group` 共用同一规则，忽略大小写，先精确匹配分组名，没有再按包含匹配
  （`/nz list aws` 能命中 `AWS`）。

## 依赖的面板接口

* `GET /api/v1/server/details` — 服务器列表 + 硬件 + 实时状态（一次请求拿全）。
  插件**不用** `?tag=`：实测该模式下 `display_index` 全为 0（面板顺序丢失）且大小写敏感，所以统一取全量后本地过滤。
* `GET /api/v1/monitor/<server_id>` — 该服务器的网络质量监控历史（魔改版特有）

鉴权用 `Authorization: <token>`（`Bearer ` 前缀也可）。未通过鉴权时 HTTP 状态码仍可能是
`200`，所以要读响应体里的 `code` 字段，插件已处理这两种情况。

在线判定与面板一致：`now - last_active <= online_threshold`。
`avg_delay == 0` 视为丢包 / 超时（与面板图表口径一致）。

## NapCat / OneBot 说明

* 卡片通过 AstrBot 的文转图（`html_render`）生成，用 `event.image_result()` 发送；
  AstrBot 的 aiocqhttp 适配器会把渲染结果 URL 转成 `base64://` 交给 NapCat，
  已实测（AstrBot 4.14.6）该链路的载荷是合法 PNG。
* AstrBot 自 v4.23 起会往文转图模板里注入约 1.2 MB 的 Shiki 代码高亮运行时；卡片模板带了
  `astrbot-t2i-shiki-runtime` 占位注释跳过注入（按 4.27.4 源码的注入函数实测：约 50 节点列表 POST 体
  1529 KiB → 71 KiB，本地 Chromium 渲染快约 200 ms），旧版本上只是一段无害注释。
* 图片较大时（如约 50 台节点、`ultra` 清晰度 PNG ≈ 3 MB，base64 后 ≈ 4.2 MB）建议调小
  `image_quality`、`max_list_rows`，或在 NapCat 上调大图片上传限制；
  实在发不出图可临时把 `output_mode` 设为 `text`。
* 长列表在移动端 QQ 里会被压缩，`monitor_in_list` 默认关闭也是为了避免卡片过高。

## 验证记录（AstrBot 4.14.6 真机链路）

* 真实框架注册与路由：`CommandFilter` 命令行名为 `nz / nezha / 哪吒 / 探针`；
  `/nz list`、`/哪吒 list`、`/探针` 均能命中 handler 并产出图片消息。
* 真实文转图：走 AstrBot `html_render` → 官方 t2i 端点，
  `device_scale_factor_level=normal|high|ultra` 实测输出宽度为 960 / 1248 / 1728 px。
* 真实 NapCat 载荷：`AiocqhttpMessageEvent._from_segment_to_dict()` 输出的
  `base64://` 解码后是合法 PNG（magic `\x89PNG`），即群聊里实际发送的字节。
* 异常与权限：渲染服务不可用时自动回退纯文本；`admin` / `whitelist` 模式按
  AstrBot 的 `event.role == "admin"` 语义放行或拒绝。
* 面板侧：错 Token、`base_url` 误带 `/api/v1`、离线节点、畸形字段（缺 CPU/内存为 0）、
  无监控节点、约 50 节点长列表均实跑通过。

## 文件

```
astrbot_plugin_nezha/
├── __init__.py
├── metadata.yaml        # 插件元数据
├── _conf_schema.json    # 后台配置表单
├── main.py              # 指令、权限、卡片/文本输出切换
├── nezha_client.py      # API 客户端、字段归一化、模糊匹配
├── formatter.py         # 纯文本渲染 + 通用格式化
├── cards.py             # Jinja2 + CSS 卡片模板与数据装配
├── requirements.txt
└── README.md
```

## 更新记录

* **v1.1.0**
  * 修复 `/nz list <分组>` 与分组卡片的序号是「组内序号」，和 `/nz <序号>` 解析到的节点对不上；
    `/nz list <分组>` 排序与面板不一致、分组名大小写敏感。
  * 修复「序号 N」与「ID N」撞号时静默按 ID 命中；现在列出两者让用户选择，候选只列并列最高分。
  * 分组卡片补上文档承诺的延迟列；列表 / 分组只为实际显示的行抓监控。
  * 跳过 AstrBot 的 Shiki 运行时注入，文转图上传体积约降为 1/20。
  * HTTP 401/403 按鉴权错误提示；响应体只解码一次；去掉未使用的顶层导入兜底。
