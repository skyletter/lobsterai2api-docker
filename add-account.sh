#!/bin/sh
# add-account.sh — 在 server 容器内交互式添加 LobsterAI 账号
# 无需临时容器、无需 --network host；回调在容器内打回，token 直接落盘 /app/auths
# 用法: docker exec -it lobsterai2api /app/add-account.sh
set -u

# 兜底环境变量（容器 compose 已配置，此处防止单独 exec 时缺失）
export LB2A_UPSTREAM_BASE="${LB2A_UPSTREAM_BASE:-https://lobsterai-server.youdao.com}"
export LB2A_LOGIN_PORTAL="${LB2A_LOGIN_PORTAL:-https://lobsterai.youdao.com}"

BIN=/app/login
LOGFILE=/tmp/lb2api-login-url.log
STATE=/tmp/lb2api-login-state.json

cd /app
rm -f "$LOGFILE" "$STATE" "$STATE.result"

echo "▶ 启动本地回调服务，请稍候..."
"$BIN" url > "$LOGFILE" 2>&1 &
PID=$!

URL=""
i=0
while [ $i -lt 100 ]; do
    URL=$(grep -m1 '^https://' "$LOGFILE" 2>/dev/null | head -1)
    [ -n "$URL" ] && break
    i=$((i+1))
    sleep 0.2
done

if [ -z "$URL" ]; then
    echo "✗ 启动登录服务失败，日志如下："
    cat "$LOGFILE"
    exit 1
fi

echo "在浏览器中打开下面的链接完成登录（手机号 / 微信）:"
echo
echo "  $URL"
echo
echo "登录成功后浏览器会回跳到 http://127.0.0.1:<port>/auth/callback?..."
echo "（提示“无法访问此网站”是正常的，这是设计好的本地回跳地址）"
echo
echo "请把地址栏中的整条 URL 复制并粘贴到下面，然后回车："
printf "回调URL> "
read CALLBACK

CODE=$(printf '%s' "$CALLBACK" | sed -n 's/.*[?&]code=\([^&]*\).*/\1/p')
PORT=$(sed -n 's/.*"port"[[:space:]]*:[[:space:]]*\([0-9]*\).*/\1/p' "$STATE" 2>/dev/null)
SVID=$(sed -n 's/.*"state"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' "$STATE" 2>/dev/null)

if [ -z "$CODE" ] || [ -z "$PORT" ] || [ -z "$SVID" ]; then
    echo "✗ 未能解析回调参数（code/port/state），请确认粘贴的是完整的登录回跳 URL"
    kill "$PID" 2>/dev/null
    exit 1
fi

echo "▶ 正在写入回调并兑换 token..."
wget -q -O /tmp/lb2api-callback-out.html \
    "http://127.0.0.1:${PORT}/auth/callback?code=${CODE}&state=${SVID}" || true

# 轮询等待兑换完成（login 超时为 10 分钟，这里只等 40s；不依赖 wait 阻塞）
i=0
while [ $i -lt 200 ]; do
    if [ -f "$STATE.result" ]; then
        break
    fi
    i=$((i+1))
    sleep 0.2
done
wait "$PID" 2>/dev/null

if [ -f "$STATE.result" ]; then
    echo "✓ 登录成功！已保存账号文件："
    ls -la /app/auths/
    echo
    echo "重启主服务加载新账号: docker restart lobsterai2api"
else
    echo "✗ 兑换失败或超时。login 日志（含真实错误）如下："
    cat "$LOGFILE"
    echo "回调响应：" 
    cat /tmp/lb2api-callback-out.html 2>/dev/null
    echo
    echo "提示：若日志是 http_error/code=..., 通常是签到版本门槛或 code 已用，可重新运行本脚本换新链接再试。"
    exit 1
fi