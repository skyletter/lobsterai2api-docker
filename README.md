# lobsterai2api-docker

将 [lobsterai2api](https://github.com/xinxinshuhao-create/lobsterai2api)（网易有道 LobsterAI 反代网关）Docker 化，**通过 GitHub Actions 自动跟随官方项目更新**，构建后的镜像推送到 GitHub Container Registry（GHCR），NAS 上一条 `docker compose` 命令即可部署生效。

## 特性

- 🚀 **自动构建**：GitHub Actions 每天定时拉取官方最新源码，检出到有更新才重建（省 Actions 额度），也可手动触发
- 🖥 **amd64 镜像**：面向主流 NAS（群晖/威联通等 x86 设备），只构建 `amd64` 单架构
- 📦 **镜像托管**：推送至 GHCR，公共仓库免登录免费拉取
- 🔄 **自动签到**：内置每日签到容器（cron 定时，默认 9 点/21 点），还有余额查询工具
- 👤 **容器内一键登录**：账号登录集成进 server 容器，`docker exec` 一条命令交互完成，无需再起临时登录容器
- 📈 **跟随更新**：官方出新 commit，工作流自动重建 `latest` 镜像，NAS `docker compose pull` 即可用新版

## 架构

```
lobsterai2api-docker/
├── .github/workflows/build-and-push.yml   # CI：定时跟随官方构建 + 推送 GHCR
├── Dockerfile                             # 主服务镜像（构建官方源码 + 登录脚本）
├── add-account.sh                         # 容器内一键添加账号的交互脚本
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
| `ghcr.io/<owner>/lobsterai2api-docker/server:latest`  | 主服务（OpenAI 兼容网关 + 登录） |
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

创建数据目录（**必须 chown 给容器用户 10001**，否则 login/签到写不进去）：

```bash
mkdir -p auths data
chown -R 10001:10001 auths data
```

### 2. 下载 compose.yaml 并启动

将本仓库 `compose.yaml` 放到同一目录（或直接按上文内容创建），然后：

```bash
docker compose up -d
```

> 如果 NAS 没装 Compose 插件（老版群晖），用 `docker-compose up -d`。

安装内核版本建议使用我们的官方 Compose 规范（`compose.yaml`），环境变量如 `LB2A_UPSTREAM_BASE` 直接写 URL 即可，**不要加反引号或引号包裹**，否则值会变成带特殊符号的字符串导致连不上上游。

### 3. 添加账号（在 server 容器内一键完成，无需临时容器）

方法一（推荐），进入 server 容器：

```bash
docker exec -it lobsterai2api /app/add-account.sh
```

脚本会：

1. 打印一条登录链接，在浏览器打开完成手机号/微信登录；
2. 登录后浏览器会回跳到 `http://127.0.0.1:<port>/auth/callback?...`（NAS 在远程时地址栏提示「无法访问此网站」是正常现象）；
3. 把地址栏整条 URL 复制粘贴回终端，脚本自动完成 "回调打回 → 换 token → 落盘 `/app/auths`"。

提示 `✓ 登录成功！已保存账号文件` 后重启主服务加载：

```bash
docker restart lobsterai2api
curl -s http://127.0.0.1:8367/status
```

方法二，原官方流程（临时容器 + host 网络），仅当方法一不适用时使用：

```bash
mkdir -p /tmp/lb2api && chown -R 10001:10001 /tmp/lb2api
docker run -d --rm --name lb2api-login --network host -u 10001:10001 \
  -v "$PWD/auths":/app/auths \
  -e LB2A_UPSTREAM_BASE=https://lobsterai-server.youdao.com \
  -e LB2A_LOGIN_PORTAL=https://lobsterai.youdao.com \
  --entrypoint /app/login \
  ghcr.io/skyletter/lobsterai2api-docker/server:latest url

docker logs lb2api-login   # 复制输出的登录链接
```

浏览器登录后，把地址栏回调 URL 打回（见官方文档说明），成功后 `docker rm -f lb2api-login` 并 `docker restart lobsterai2api`。

多账号时：同一浏览器登录新号前先退出旧账号，或使用无痕窗口。新增账号 `/status` 里 `credits` 显示 0 属正常，等下一次余额刷新即可。

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