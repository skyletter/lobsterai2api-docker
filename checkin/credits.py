#!/usr/bin/env python3
"""查所有号的额度明细与每个批次的有效期（只读 profile-summary，零成本）。"""
import datetime as dt
import json
import pathlib
import sys
import urllib.error
import urllib.request

BASE = "https://lobsterai-server.youdao.com"
CLIENT_VERSION = "2026.9.4"
AUTHS = pathlib.Path(__file__).resolve().parent / "auths"
CST = dt.timezone(dt.timedelta(hours=8))   # 接口时间戳是北京时间但不带时区


def parse_exp(s):
    s = str(s).strip().replace("Z", "+00:00")
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        d = dt.datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    return d.replace(tzinfo=CST) if d.tzinfo is None else d.astimezone(CST)


def summary(uid):
    tok = json.loads((AUTHS / f"lobsterai-{uid}.json").read_text())["auth"]["accessToken"]
    req = urllib.request.Request(BASE + "/api/user/profile-summary", headers={
        "Authorization": "Bearer " + tok,
        "Accept": "application/json",
        "User-Agent": "LobsterAI/" + CLIENT_VERSION,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())["data"]


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else None
    files = sorted(AUTHS.glob("lobsterai-*.json"))
    if want:
        files = [f for f in files if f.stem == f"lobsterai-{want}"]
    if not files:
        print(f"没有找到账号文件：{AUTHS}/lobsterai-*.json"
              + (f"（没有 uid={want} 的号）" if want else ""))
        return 1

    now = dt.datetime.now(CST)
    fails, rows, soon = 0, [], []
    for f in files:
        uid = f.stem.split("-", 1)[1]
        try:
            d = summary(uid)
            if not isinstance(d, dict):
                raise ValueError("响应 data 为空（通常是 accessToken 失效）")
        except urllib.error.HTTPError as e:
            hint = "（token 过期 → 重走一遍登录流程）" if e.code in (401, 403) else ""
            print(f"❌ {uid}：HTTP {e.code} {hint}")
            fails += 1
            continue
        except Exception as e:
            print(f"❌ {uid}：{e}")
            fails += 1
            continue

        items = sorted(d.get("creditItems") or [], key=lambda x: x["expiresAt"])
        total = d.get("totalCreditsRemaining")
        rows.append((uid, d.get("nickname", ""), total))
        print(f"\n=== {uid} {d.get('nickname','')}：合计 {total} 分 ===")
        if not items:
            print("  （没有未过期批次）")
        for it in items:
            exp = parse_exp(it["expiresAt"])
            days = (exp - now).total_seconds() / 86400
            flag = "   ⚠️ 7 天内到期" if days < 7 else ""
            print(f"  [{it['type']}] {it['label']}  {it['creditsRemaining']:g} 分"
                  f"   到期 {exp:%Y-%m-%d %H:%M}   剩 {days:.1f} 天{flag}")
            if days < 7:
                soon.append((days, uid, it["creditsRemaining"]))
        s = sum(i["creditsRemaining"] for i in items)
        if total is not None and abs(s - total) > 0.01:
            print(f"  ⚠️ 批次合计 {s:g} ≠ totalCreditsRemaining {total}（口径不一致，留意）")

    if rows:
        print("\n" + "-" * 46)
        for uid, nick, total in rows:
            print(f"  {uid} {nick}：{total} 分")
        print(f"  合计 {sum((r[2] or 0) for r in rows):g} 分 / {len(rows)} 个号")
    for days, uid, c in sorted(soon):
        print(f"  ⚠️ {uid} 有 {c:g} 分将在 {days:.1f} 天内到期")
    print(f"\n[{dt.datetime.now(CST):%Y-%m-%d %H:%M:%S}] 结束，失败 {fails} 个")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())