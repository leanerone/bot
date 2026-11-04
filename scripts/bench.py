"""简易压测: 并发问答延迟统计。

用法: python scripts/bench.py --users 5 --rounds 4 [--base http://127.0.0.1:8100]
账号用 config bootstrap_users 中的 user 角色 (viewer 也可以)。
"""
import argparse
import concurrent.futures
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

QUESTIONS = [
    "最近未处理的告警有哪些",
    "射频功率漂移怎么处理",
    "机台状态怎么查",
    "最近一周 P1234 的平均良率",
    "交班时最容易被漏掉的信息有哪些",
]


def one_round(base: str, user: str, pw: str, q: str) -> dict:
    t0 = time.time()
    with httpx.Client(base_url=base, timeout=60) as c:
        r = c.post("/api/auth/login", json={"username": user, "password": pw})
        assert r.status_code == 200, r.text
        resp = c.post("/api/chat", json={"question": q})
        ms = int((time.time() - t0) * 1000)
        return {"ms": ms, "status": resp.status_code, "type": resp.json().get("type")}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="http://127.0.0.1:8100")
    parser.add_argument("--users", type=int, default=5, help="并发用户数")
    parser.add_argument("--rounds", type=int, default=4, help="每人轮数")
    parser.add_argument("--user", default="zhangsan")
    parser.add_argument("--password", default="user123")
    args = parser.parse_args()

    jobs = []
    with concurrent.futures.ThreadPoolExecutor(args.users) as ex:
        for u in range(args.users):
            for r in range(args.rounds):
                q = QUESTIONS[(u + r) % len(QUESTIONS)]
                jobs.append(ex.submit(one_round, args.base, args.user, args.password, q))
        results = [j.result() for j in jobs]

    ok = [r for r in results if r["status"] == 200]
    rate_limited = [r for r in results if r["status"] == 429]
    errors = [r for r in results if r["status"] not in (200, 429)]
    lat = sorted(r["ms"] for r in ok)

    print(f"总请求 {len(results)} | 成功 {len(ok)} | 限流 {len(rate_limited)} | 错误 {len(errors)}")
    if lat:
        print(f"延迟 ms: p50={lat[len(lat)//2]} min={lat[0]} max={lat[-1]} "
              f"avg={round(statistics.mean(lat))}")
    if errors:
        print("错误样例:", errors[:3])
    # 注意: 默认限流 30 次/分钟/用户, 压测可能触发 429 —— 属预期保护行为


if __name__ == "__main__":
    main()
