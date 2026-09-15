# lobsterai2api-docker

将 [lobsterai2api](https://github.com/xinxinshuhao-create/lobsterai2api)（网易有道 LobsterAI 反代网关）Docker 化，**通过 GitHub Actions 自动跟随官方项目更新**，构建后的镜像推送到 GitHub Container Registry（GHCR），NAS 上一条 `docker compose` 命令即可部署生效。

## 特性

- 🚀 **自动构建**：GitHub Actions 每天定时拉取官方最新源码，检出到有更新才重建（省 Actions 额度），也可手动触发
- 🖥 **多架构**：同时构建 `amd64` 与 `arm64`，兼容群晖/威联通等主流 NAS
- 📦 **镜像托管**：推送至 GHCR，NAS 免费免登录拉取（公共仓库）
- 🔄 **自动签到**：内置每日签到容器（cron 定时，默认 9 点/21 点），还有余额查询工具
- 📈 **跟随更新**：官方出新 commit，工作流自动重建 `latest` 镜像，NAS `docker compose pull` 即可用新版

## 架构

```
lobsterai2api-docker/
├── .github/workflows/build-and-push.yml   # CI：定时跟随官方构建 + 推送 GHCR
├── Dockerfile                             # 主服务镜像（构建官方源码）
├── compose.yaml                           # NAS 一键部署（server + checkin）
├── config.example.json                    # 配置模板
└── checkin/                               # 每日签到容器
    ├── Dockerfile
    ├── entrypoint.sh                      # cron 入口
    ├── checkin.py                         # 每日签到
    └── credits.py                         # 额度/到期查询
```

## 镜像

| 镜像                          | 说明                     |
| ----------------------------- | ------------------------ |
| `ghcr.io/<owner>/lobsterai2api-docker/server:latest`  | 主服务（OpenAI 兼容网关） |
| `ghcr.io/<owner>/lobsterai2api-docker/checkin:latest` | 每日签到 + 余额查询       |

> 本仓库即 `ghcr.io/skyletter/lobsterai2api-docker`。若 fork 到别的账号，请全局替换 compose 中的 `skyletter` 为你自己的 GitHub 用户名。

## 部署到 NAS

### 1. 准备目录与配置

在 NAS 上创建项目目录（在群晖中即共享文件夹）：

```bash
mkdir -p lobsterai2api && cd lobsterai2api
```

创建 `config.json`（复制 `config.example.json`，**必须改 `api_key` 为任意自定义密钥**，这是你客户端访问的密码）：

```json
{
  "listen": ":8367",
  "api_key": "CHANGE_ME_custom_api_key",
  "auth_dir": "/app/auths",
  "state_file": "/app/data/state.json",
  "cooldown": {"hard_credit": "12h", "soft_rate": "60s", "err_threshold": 3, "err_cooldown": "10m"},
  "schedule": {"checkin_hours": [9, 21], "keepalive_hours": [22]},
  "upstream": {"timeout_seconds": 180}
}
```

创建数据目录：

```bash
mkdir -p auths data
```

### 2. 下载 compose.yaml 并启动

将本仓库 `compose.yaml` 放到同一目录（或直接按上文内容创建），然后：

```bash
docker compose up -d
```

> 如果 NAS 没装 Compose 插件（老版群晖），用 `docker-compose up -d`。

### 3. 账号登录（一次性）

官方登录依赖本地回环回调，需在 NAS 上跑一个临时登录容器（`--network host`）：

```bash
docker run -d --name lb2api-login --network host -u 10001:10001 \
  -v "$PWD/auths":/app/auths \
  -e LB2A_UPSTREAM_BASE=https://lobsterai-server.youdao.com \
  -e LB2A_LOGIN_PORTAL=https://lobsterai.youdao.com \
  --entrypoint /app/login \
  ghcr.io/skyletter/lobsterai2api-docker/server:latest url

docker logs lb2api-login   # 复制输出的 https://lobsterai.youdao.com/portal#/login?... 链接
```

拿链接在浏览器里登录（**NAS 在远程时**：登录后地址栏变成 `http://127.0.0.1:xxxxx/auth/callback?...` 提示无法访问是正常的，整条 URL 复制出来，把回调打回容器）：

```bash
docker exec lb2api-login login url   # 如果容器日志被截断可再取一次
# 将回调 URL 发回容器（参照官方说明，port/state 从容器内 /tmp/lb2api-login-state.json 读取）
```

登录成功提示 `auth saved` 后删除临时容器并重启主服务：

```bash
docker rm -f lb2api-login
docker restart lobsterai2api
curl -s http://127.0.0.1:8367/status
```

多账号时：同一浏览器登录新号前先退出旧账号，或使用无痕窗口。

### 4. 验证

```bash
curl -s http://127.0.0.1:8367/v1/chat/completions \
  -H "Authorization: Bearer CHANGE_ME_custom_api_key" \
  -H 'Content-Type: application/json' \
  -d '{"model": "deepseek-flash", "messages": [{"role": "user", "content": "你好"}], "stream": false}'
```

### 5. 查看签到与余额

```bash
# 签到日志（checkin 容器每天 9/21 点自动跑，启动时也会立即跑一次）
docker logs lobsterai2api-checkin

# 手动查余额明细
docker exec lobsterai2api-checkin python3 /app/checkin/credits.py
```

## 跟随官方更新

工作流 `build-and-push.yml` 每天北京时间 10:00 自动检查官方仓库：

- 官方有新 commit → 构建并推送新的 `latest` 镜像
- 没有新 commit → 跳过（不消耗 Actions 额度）

手动触发构建（比如立刻要最新版）：

```bash
gh workflow run build-and-push.yml
```

NAS 侧更新到最新镜像：

```bash
cd lobsterai2api && docker compose pull && docker compose up -d
```

## License

MIT，跟随上游 [lobsterai2api](https://github.com/xinxinshuhao-create/lobsterai2api)。