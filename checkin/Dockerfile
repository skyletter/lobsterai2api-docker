# 每日签到 + 余额查询容器：定时运行 checkin.py / credits.py
# 与主服务共享 auths 目录（只读）与 data 日志目录
FROM python:3.12-alpine

RUN apk add --no-cache tzdata && \
    mkdir -p /app/checkin/auths /app/checkin/data && \
    adduser -D -u 10001 -h /app app && \
    chown -R 10001:10001 /app

WORKDIR /app/checkin
COPY checkin.py credits.py entrypoint.sh ./
RUN chmod +x entrypoint.sh

# 需要 root 运行 crond，因此不降权
ENTRYPOINT ["/app/checkin/entrypoint.sh"]