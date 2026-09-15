#!/usr/bin/env python3
"""有道 LobsterAI 每日签到（+100 积分/号/天）。"""
import json
import pathlib
import sys
import urllib.request
import uuid

BASE = "https://lobsterai-server.youdao.com"
CLIENT_VERSION = "2026.9.4"   # 必须是官方客户端版本门槛，写低了一律 slotState=empty
AUTHS = pathlib.Path(__file__).resolve().parent / "auths"


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
        try:
            msg, gained = checkin(uid, doc["auth"]["accessToken"])
            print(f"[{uid}] {msg}" + (f" 积分 +{gained:g}" if gained else ""))
        except Exception as e:
            print(f"[{uid}] 签到失败：{e}")
            fails += 1
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())