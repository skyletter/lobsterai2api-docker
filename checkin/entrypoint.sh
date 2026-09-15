#!/bin/sh
set -e

# 设置时区
if [ -n "$TZ" ] && [ -f "/usr/share/zoneinfo/$TZ" ]; then
    ln -sf "/usr/share/zoneinfo/$TZ" /etc/localtime
    echo "$TZ" > /etc/timezone
fi

mkdir -p /app/checkin/auths /app/checkin/data

# 签到时刻：默认 9 点和 21 点，可用 CHECKIN_HOURS 覆盖（如 "9,21"）
HOURS="${CHECKIN_HOURS:-9,21}"

# 写 crontab（busybox crond，5 分钟固定秒偏移）
cat > /etc/crontabs/root <<EOF
5 ${HOURS} * * * /usr/local/bin/python3 /app/checkin/checkin.py >> /app/checkin/data/checkin.log 2>&1
EOF

echo "checkin cron set: 5 ${HOURS} * * *"

# 启动时立即跑一次签到（幂等：当天已签会跳过）
/usr/local/bin/python3 /app/checkin/checkin.py >> /app/checkin/data/checkin.log 2>&1 || true

exec /usr/sbin/crond -f -l 2