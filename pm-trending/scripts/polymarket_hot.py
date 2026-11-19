#!/usr/bin/env python3
"""采集 Polymarket 当前热门事件，输出热点话题和市场预期。

数据来源：Polymarket 公开的 Gamma API（只读，无需登录、无需钱包）。

用法：
    python3 scripts/polymarket_hot.py                 # 默认：按 24h 成交量取前 100 个事件，排除体育/电竞
    python3 scripts/polymarket_hot.py --limit 200     # 采集更多事件
    python3 scripts/polymarket_hot.py --include-sports
    python3 scripts/polymarket_hot.py --top 30        # 报告中展示前 30 个事件

输出（相对模块目录 pm-trending/）：
    data/snapshots/<时间戳>.json.gz   完整快照（保留以便日后做时间序列）
    data/snapshots/<时间戳>.csv.gz    每个子市场一行，方便用 pandas 分析
    reports/latest.md              可读的中文报告
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

API = "https://gamma-api.polymarket.com/events"
EVENT_URL = "https://polymarket.com/event/"
ROOT = Path(__file__).resolve().parent.parent  # 模块目录 pm-trending/

SPORTS_TAGS = {"Sports", "Esports", "Games"}
# 这些标签不代表话题，汇总话题热度时忽略
NOISE_TAGS = {"Hide From New", "Recurring", "Games", "All", "Featured", "Yearly",
              "Weekly", "Daily", "Main Election", "Hit Price", "Tweet Markets"}


def fetch_events(limit: int, page_size: int = 50) -> list[dict]:  # API 拒绝 limit>50（返回 406）
    events: list[dict] = []
    offset = 0
    while len(events) < limit:
        params = {
            "active": "true", "closed": "false", "archived": "false",
            "order": "volume24hr", "ascending": "false",
            "limit": min(page_size, limit - len(events)), "offset": offset,
        }
        url = f"{API}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": "pm-research/0.1"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            batch = json.load(resp)
        if not batch:
            break
        events.extend(batch)
        offset += len(batch)
        time.sleep(0.3)  # 对公开 API 客气一点
    return events


def _json_list(value) -> list:
    if isinstance(value, list):
        return value
    try:
        return json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []


def yes_probability(m: dict) -> float | None:
    """优先用买卖中间价，盘口太宽时退回到 outcomePrices。"""
    bid, ask = m.get("bestBid"), m.get("bestAsk")
    if bid is not None and ask is not None and 0 < ask - bid <= 0.1:
        return (bid + ask) / 2
    prices = _json_list(m.get("outcomePrices"))
    outcomes = _json_list(m.get("outcomes"))
    if prices and outcomes:
        try:
            idx = outcomes.index("Yes") if "Yes" in outcomes else 0
            return float(prices[idx])
        except (ValueError, IndexError):
            return None
    return None


def summarize_event(e: dict) -> dict:
    tags = [t.get("label") for t in e.get("tags") or [] if t.get("label")]
    outcomes = []
    for m in e.get("markets") or []:
        if m.get("closed") or not m.get("active", True):
            continue
        p = yes_probability(m)
        if p is None:
            continue
        outcomes.append({
            "name": m.get("groupItemTitle") or m.get("question"),
            "question": m.get("question"),
            "prob": p,
            "change_1d": m.get("oneDayPriceChange"),
            "change_1w": m.get("oneWeekPriceChange"),
            "volume24hr": float(m.get("volume24hr") or 0),
            "volume": float(m.get("volumeNum") or m.get("volume") or 0),
            "outcome_labels": _json_list(m.get("outcomes")),
        })
    outcomes.sort(key=lambda o: o["prob"], reverse=True)
    return {
        "id": e.get("id"),
        "title": e.get("title"),
        "url": EVENT_URL + (e.get("slug") or ""),
        "tags": tags,
        "volume24hr": float(e.get("volume24hr") or 0),
        "volume1wk": float(e.get("volume1wk") or 0),
        "volume": float(e.get("volume") or 0),
        "liquidity": float(e.get("liquidity") or 0),
        "end_date": (e.get("endDate") or "")[:10],
        "outcomes": outcomes,
    }


def is_sports(ev: dict) -> bool:
    return bool(SPORTS_TAGS & set(ev["tags"]))


def topic_ranking(events: list[dict]) -> list[tuple[str, float, int]]:
    agg: dict[str, list] = defaultdict(lambda: [0.0, 0])
    for ev in events:
        # "Rewards ..." / "Earn ..." 是平台的流动性激励标签，不是话题
        for t in {t for t in ev["tags"] if not t.startswith(("Rewards", "Earn"))} - NOISE_TAGS:
            agg[t][0] += ev["volume24hr"]
            agg[t][1] += 1
    return sorted(((t, v, n) for t, (v, n) in agg.items()), key=lambda x: x[1], reverse=True)


def top_movers(events: list[dict], min_vol: float = 20_000, n: int = 15) -> list[tuple[dict, dict]]:
    pairs = [(ev, o) for ev in events for o in ev["outcomes"]
             if o["change_1d"] is not None and o["volume24hr"] >= min_vol]
    pairs.sort(key=lambda x: abs(x[1]["change_1d"]), reverse=True)
    return pairs[:n]


def money(v: float) -> str:
    if v >= 1e6:
        return f"${v / 1e6:.1f}M"
    if v >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:.0f}"


def pct(p: float) -> str:
    return f"{p * 100:.1f}%" if p >= 0.01 else "<1%"


def signed_pp(c: float | None) -> str:
    return "—" if c is None else f"{c * 100:+.1f}pp"


def describe_expectation(ev: dict, k: int = 3) -> str:
    outs = ev["outcomes"]
    if not outs:
        return "—"
    if len(outs) == 1:
        o = outs[0]
        label = o["outcome_labels"][0] if o["outcome_labels"] else "Yes"
        return f"{label} {pct(o['prob'])}（24h {signed_pp(o['change_1d'])}）"
    return "；".join(f"{o['name']} {pct(o['prob'])}" for o in outs[:k])


def md_cell(s: str) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def write_report(events: list[dict], ts: str, top: int, sports_excluded: bool) -> Path:
    lines = [
        "# Polymarket 热点与市场预期",
        "",
        f"采集时间：{ts} UTC　|　事件数：{len(events)}"
        + ("　|　已排除体育/电竞" if sports_excluded else ""),
        "",
        "> 概率取自买卖中间价（盘口过宽时取最新报价），只代表市场定价，不是事实，也不是投资建议。",
        "",
        "## 话题热度（按 24h 成交额汇总标签）",
        "",
        "| 排名 | 话题标签 | 24h 成交额 | 事件数 |",
        "|---|---|---|---|",
    ]
    for i, (t, v, n) in enumerate(topic_ranking(events)[:20], 1):
        lines.append(f"| {i} | {md_cell(t)} | {money(v)} | {n} |")

    lines += ["", f"## 最热门的 {min(top, len(events))} 个事件", "",
              "| # | 事件 | 24h 成交额 | 总成交额 | 截止 | 市场预期（最高概率选项） |",
              "|---|---|---|---|---|---|"]
    for i, ev in enumerate(events[:top], 1):
        title = f"[{md_cell(ev['title'])}]({ev['url']})"
        lines.append(f"| {i} | {title} | {money(ev['volume24hr'])} | {money(ev['volume'])} "
                     f"| {ev['end_date']} | {md_cell(describe_expectation(ev))} |")

    lines += ["", "## 预期变化最大的市场（24h 概率变动，24h 成交额 ≥ $20K）", "",
              "| 事件 | 选项 / 问题 | 当前概率 | 24h 变动 |", "|---|---|---|---|"]
    for ev, o in top_movers(events):
        lines.append(f"| {md_cell(ev['title'])} | {md_cell(o['name'])} | {pct(o['prob'])} "
                     f"| {signed_pp(o['change_1d'])} |")

    out = ROOT / "reports" / "latest.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def write_snapshot(events: list[dict], stamp: str) -> tuple[Path, Path]:
    snap_dir = ROOT / "data" / "snapshots"
    snap_dir.mkdir(parents=True, exist_ok=True)
    jpath = snap_dir / f"{stamp}.json.gz"
    with gzip.open(jpath, "wt", encoding="utf-8") as f:
        json.dump(events, f, ensure_ascii=False)

    # pandas 可直接读取：pd.read_csv("xxx.csv.gz")
    cpath = snap_dir / f"{stamp}.csv.gz"
    with gzip.open(cpath, "wt", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["snapshot", "event_id", "event_title", "tags", "event_volume24hr",
                    "event_volume", "end_date", "outcome", "prob", "change_1d",
                    "change_1w", "market_volume24hr", "url"])
        for ev in events:
            for o in ev["outcomes"]:
                w.writerow([stamp, ev["id"], ev["title"], ";".join(ev["tags"]),
                            round(ev["volume24hr"], 2), round(ev["volume"], 2), ev["end_date"],
                            o["name"], round(o["prob"], 4), o["change_1d"], o["change_1w"],
                            round(o["volume24hr"], 2), ev["url"]])
    return jpath, cpath


def print_summary(events: list[dict], n: int = 15) -> None:
    print("\n话题热度 Top 10：")
    for t, v, c in topic_ranking(events)[:10]:
        print(f"  {t:<24} {money(v):>8}  ({c} 个事件)")
    print(f"\n热门事件 Top {n}：")
    for i, ev in enumerate(events[:n], 1):
        print(f"{i:>3}. {ev['title'][:60]:<60} {money(ev['volume24hr']):>8}")
        print(f"     → {describe_expectation(ev)}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=100, help="按 24h 成交额抓取的事件数（排除体育前）")
    ap.add_argument("--top", type=int, default=25, help="报告中列出的事件数")
    ap.add_argument("--include-sports", action="store_true", help="保留体育/电竞单场比赛")
    args = ap.parse_args()

    now = datetime.now(timezone.utc)
    raw = fetch_events(args.limit)
    events = [summarize_event(e) for e in raw]
    if not args.include_sports:
        events = [ev for ev in events if not is_sports(ev)]
    events.sort(key=lambda ev: ev["volume24hr"], reverse=True)

    stamp = now.strftime("%Y%m%d-%H%M")
    jpath, cpath = write_snapshot(events, stamp)
    report = write_report(events, now.strftime("%Y-%m-%d %H:%M"), args.top, not args.include_sports)

    print_summary(events)
    print(f"\n已保存：\n  {report.relative_to(ROOT)}\n  {jpath.relative_to(ROOT)}\n  {cpath.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
