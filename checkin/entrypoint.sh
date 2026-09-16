#!/bin/sh
set -e

# 设置时区
if [ -n "$TZ" ] && [ -f "/usr/share/zoneinfo/$TZ" ]; then
    ln -sf "/usr/share/zoneinfo/$TZ" /etc/localtime
    echo "$TZ" > /etc/timezone
fi

mkdir -p /app/checkin/auths /app/checkin/data

# 启动自检：auths 必须能读到账号文件（应挂载 server 的 auths 目录）
if ! ls /app/checkin/auths/lobsterai-*.json >/dev/null 2>&1; then
    echo "⚠️  警告：/app/checkin/auths 下没有账号文件（lobsterai-*.json）。"
    echo "   请确认 checkin 容器挂载的是 server 容器的 auths 目录（同一个）。"
    echo "   登录过但找不到账号？请检查 compose 挂载路径。"
fi

# 签到时刻：默认 9 点和 21 点，可用 CHECKIN_HOURS 覆盖（如 "9,21"）
HOURS="${CHECKIN_HOURS:-9,21}"

# 写 crontab（busybox crond，5 分钟固定秒偏移）。
# 签到输出同时进 docker logs（tee）和日志文件，便于排查
cat > /etc/crontabs/root <<EOF
5 ${HOURS} * * * /usr/local/bin/python3 /app/checkin/checkin.py 2>&1 | tee -a /app/checkin/data/checkin.log
EOF

echo "checkin cron set: 5 ${HOURS} * * *"

# 启动时立即跑一次签到（幂等：当天已签会跳过），输出同时进 docker logs
echo "===== 启动时立即签到一次 ====="
/usr/local/bin/python3 /app/checkin/checkin.py 2>&1 | tee -a /app/checkin/data/checkin.log || true

exec /usr/sbin/crond -f -l 2