# proxy-fleet

一行命令管理多台 VPS 代理节点：部署 [3x-ui](https://github.com/MHSanaei/3x-ui) + VLESS+Reality，自动生成 [Clash/Mihomo](https://github.com/MetaCubeX/mihomo) 订阅链接，增删节点后自动同步。

## 特性

- **一键部署** — 自动安装 3x-ui、扫描端口冲突并选择可用端口、配置 VLESS+Reality、开放防火墙、更新订阅文件，全部在一个 `deploy` 命令完成
- **订阅同步** — 从每个节点的 API 拉取实时状态，重新生成 Clash YAML，订阅永远反映真实配置
- **NAT 支持** — `--nat 10000-10009` 自动在端口段内选择可用端口
- **舰队状态** — 并行健康检查，显示所有节点的连通性、流量统计和可选月流量额度使用情况
- **模块化规则** — AI 服务、流媒体、通用代理、国内直连规则分文件管理，改完 `sync` 即生效

## 环境要求

- Python 3.8+（仅使用标准库，无需 pip 安装依赖）
- 通过 `~/.ssh/config` 配置好 SSH 密钥登录到各 VPS
- 本机有 `curl`（用于连通性检测）
- VPS 系统为 Debian/Ubuntu（其他发行版未测试）

## 快速开始

```bash
# 1. 克隆
git clone https://github.com/oaker-io/proxy-fleet.git
cd proxy-fleet

# 2. 交互式初始化 — 生成 config.json
python3 scripts/fleet.py init

# 3. 部署到第一台 VPS
python3 scripts/fleet.py deploy my-vps --name "Tokyo" --emoji "🇯🇵"

# 4. 查看状态
python3 scripts/fleet.py status
```

## 命令一览

```
init                                    交互式创建配置文件
status                                  查看所有节点状态（并行检查）
deploy <host> [host...]                 部署到一台或多台 SSH 主机
deploy <host> --nat 10000-10009         NAT 机器指定端口范围
deploy <host> --name "名称" --emoji "🇺🇸"  自定义节点显示名
remove <host>                           从订阅中移除节点
sync                                    从所有节点重新生成并上传订阅文件
```

## 工作原理

### 部署流程

```
SSH 连接 → 扫描已占用端口 → 自动选可用端口
  → 安装 3x-ui（若未安装）→ CLI 重置面板凭证
  → Xray 生成 x25519 密钥 → API 创建 VLESS+Reality 入站
  → 检测防火墙类型（ufw/iptables/无）→ 开放端口
  → 验证连通性 → 写入 config.json → 同步订阅
```

### 订阅托管

生成的 Clash YAML 通过 SSH 上传到指定 VPS，用 nginx + SSL 提供 HTTPS 访问（推荐 Cloudflare 代理）。用户在 Clash Verge Rev / Mihomo 中导入订阅 URL 即可获取全部节点和分流规则。

### 代理分组

| 分组 | 用途 |
|------|------|
| 🤖 AI Services | OpenAI、Claude、Gemini、Copilot、Cursor、Midjourney 等 — 优先走美国节点 |
| 🚀 Proxy | Google、GitHub、Twitter、Telegram、Discord 等 — 优先走低延迟节点 |
| 🎬 Streaming | YouTube、Netflix、Spotify、Twitch |
| 🐟 Final | 兜底规则 |

## 文件结构

```
proxy-fleet/
├── config.json              # 舰队状态（含凭证，已 gitignore）
├── config.example.json      # 新用户配置模板
├── scripts/
│   └── fleet.py             # 主脚本
└── templates/rules/
    ├── ai.yaml              # AI 服务分流规则
    ├── proxy.yaml           # 常用代理站点规则
    ├── streaming.yaml       # 流媒体规则
    └── direct.yaml          # 国内直连 / 局域网规则
```

## 更新规则

编辑 `templates/rules/` 下的对应文件，然后：

```bash
python3 scripts/fleet.py sync
```

用户在 Clash Verge Rev 中刷新订阅即可拿到最新规则。

## 运维安全边界

`proxy-fleet` 会修改远端 VPS 状态，部署前先确认影响范围：

- `deploy` 会在目标机器安装或重新配置 3x-ui。
- `deploy` 检测到限制性防火墙时，会开放选中的 VLESS 端口和 3x-ui 面板端口。
- `deploy` 只删除 `remark` 与当前节点匹配的已有 VLESS 入站，避免重复；不会删除其它手工创建的 VLESS 入站。
- `remove` 只从本地 `config.json` 和订阅中移除节点；不会卸载 3x-ui、关闭防火墙端口或删除远端入站。
- `config.json` 含面板凭证和节点状态，已 gitignore，不能提交。

## 验证

每次部署或更新规则后运行：

```bash
python3 scripts/fleet.py status
python3 scripts/fleet.py sync
curl -I https://你的订阅域名/你的URL路径/config.yaml
```

然后在 Clash Verge Rev / Mihomo 中刷新订阅，并测试至少一个需要代理的域名。

远端排障可用：

```bash
ssh <host> 'systemctl status x-ui --no-pager'
ssh <host> 'ss -tlnp | grep -E "(:443|:9453)"'
```

## 开发

运行时和测试都只使用 Python 标准库：

```bash
python3 -m py_compile scripts/fleet.py
python3 -m unittest -v tests/test_fleet.py
```

## 流量额度元信息

在 `config.json` 的节点里加 `traffic_limit_gb`，`status` 就会显示月流量额度使用情况：

```json
{
  "name": "Los Angeles",
  "traffic_limit_gb": 1000,
  "plan": "BandwagonHost 1C2G 1TB/month"
}
```

这个字段只是套餐元信息；实际 `up/down` 计数仍由 3x-ui 返回。

## 技术备注

- **Xray v26 密钥格式**：`x25519` 输出 `PrivateKey` / `Password` 或 `Password (PublicKey)`（= 公钥）/ `Hash32`。旧版输出 `Private key` / `Public key`。脚本兼容这些格式。
- **3x-ui 安装脚本**是交互式的，无法可靠 pipe 输入。策略是先装默认配置，再通过 CLI 重置凭证。
- **3x-ui API**：`POST /login` → 获取 session cookie → `/panel/api/inbounds/{add,update,del,list}`。新版 3x-ui 可能用自签 HTTPS 提供面板，脚本会先试 HTTPS，再 fallback HTTP。
- **Reality 对非 VLESS 客户端返回 400** — 连通性检测时 400 = 节点正常。
- **端口冲突**是最常见的部署失败原因 — 脚本会在配置前先扫描端口。
- **UFW 检测**必须匹配 `Status: active`，不能用 substring，因为 `inactive` 里也包含 `active`。
- **远程脚本参数**通过 `shlex.quote` 做 shell quoting，节点名和凭证可以包含空格或引号。
- **DNS IPv6** 可通过 `defaults.dns.ipv6` 配置；默认 `false`，保证客户端兼容性。
- **xray 二进制**路径自动检测（glob `/usr/local/x-ui/bin/xray-linux-*`），同时支持 amd64 和 arm64。

## 许可证

[MIT](LICENSE)
