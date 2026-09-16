#!/usr/bin/env python3
"""有道 LobsterAI 每日签到（+100 积分/号/天），签到后自动显示余额与各批次到期时间。"""
import datetime as dt
import json
import pathlib
import sys
import urllib.request
import uuid

BASE = "https://lobsterai-server.youdao.com"
CLIENT_VERSION = "2026.9.4"   # 必须是官方客户端版本门槛，写低了一律 slotState=empty
AUTHS = pathlib.Path(__file__).resolve().parent / "auths"
CST = dt.timezone(dt.timedelta(hours=8))   # 接口时间戳是北京时间但不带时区


def api(method, path, tok, body=None):
    req = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + tok,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "LobsterAI/" + CLIENT_VERSION,
        })
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read())
    if d.get("code") != 0:
        raise RuntimeError(f"code={d.get('code')} msg={d.get('message') or d.get('msg')}")
    if not isinstance(d.get("data"), dict):
        raise RuntimeError("data 为空（accessToken 可能已失效）")
    return d["data"]


def parse_exp(s):
    s = str(s).strip().replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        d = dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    return d.replace(tzinfo=CST) if d.tzinfo is None else d.astimezone(CST)


def summary(uid, tok):
    """只读 profile-summary：总余额 + 各批次到期明细。"""
    req = urllib.request.Request(BASE + "/api/user/profile-summary", headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/json",
        "User-Agent": "LobsterAI/" + CLIENT_VERSION,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"]


def print_balance(uid, tok):
    """打印余额与到期信息（查询失败不影响签到，仅提示）。"""
    try:
        d = summary(uid, tok)
    except Exception as e:
        print(f"[{uid}] 余额查询失败：{e}")
        return
    total = d.get("totalCreditsRemaining")
    now = dt.datetime.now(CST)
    items = sorted(d.get("creditItems") or [], key=lambda x: x["expiresAt"])
    line = f"[{uid}] 当前余额"
    if total is not None:
        line += f" ≈ {total:g} 分"
    print(line)
    if not items:
        print(f"[{uid}]   （无未过期批次）")
    for it in items:
        exp = parse_exp(it["expiresAt"])
        days = (exp - now).total_seconds() / 86400
        flag = " ⚠️ 7天内到期" if days < 7 else ""
        print(f"[{uid}]   [{it['type']}] {it['label']}  {it['creditsRemaining']:g} 分"
              f" 到期 {exp:%Y-%m-%d %H:%M}（剩 {days:.1f} 天{flag}）")


def checkin(uid, tok):
    q = (f"placement=desktop_sidebar&clientVersion={CLIENT_VERSION}"
         f"&containerApiVersion=2&platform=win32")
    slot = api("GET", f"/api/client-activities/slot?{q}", tok)
    if slot.get("slotState") != "available" or not slot.get("activity"):
        return "无可用活动", None
    code = slot["activity"]["activityCode"]
    rev = slot["activity"]["configRevision"]
    ctx = api("GET", f"/api/client-activities/{code}/context?configRevision={rev}", tok)
    if ctx["state"].get("claimedToday") or "check_in" not in (ctx.get("actions") or []):
        return "今天已签到，跳过", None
    res = api("POST", f"/api/client-activities/{code}/actions/check_in", tok,
              {"configRevision": rev, "idempotencyKey": str(uuid.uuid4()), "payload": {}})
    result = res.get("result") or {}
    gained = next((result[k] for k in ("creditsGranted", "rewardCredits", "credits")
                   if isinstance(result.get(k), (int, float))), None)
    return "签到成功", gained


def main():
    files = sorted(AUTHS.glob("lobsterai-*.json"))
    if not files:
        print(f"没找到账号文件：{AUTHS}/lobsterai-*.json")
        return 1
    fails = 0
    for f in files:
        doc = json.loads(f.read_text())
        uid = doc["account"]["uid"]
        tok = doc["auth"]["accessToken"]
        try:
            msg, gained = checkin(uid, tok)
            print(f"[{uid}] {msg}" + (f" 积分 +{gained:g}" if gained else ""))
        except Exception as e:
            print(f"[{uid}] 签到失败：{e}")
            fails += 1
            continue
        # 签到完成后展示余额与到期信息
        print_balance(uid, tok)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())