# pm-trending · Polymarket 热点事件与市场预期

> 本目录是 `prediction-market-research` 仓库的需求模块；仓库约定见 [../README.md](../README.md)。

从 Polymarket 公开的 Gamma API（只读，零 key、零成本）抓取当前 24h 成交额最高的事件，汇总话题热度、
热门事件各选项概率、24h 预期变化最大的市场，并保存完整快照，供后续做时间序列分析。只用 Python 标准库。

## 运行

```bash
python3 scripts/polymarket_hot.py                  # 默认抓 100 个事件，排除体育/电竞
python3 scripts/polymarket_hot.py --limit 200 --top 30
python3 scripts/polymarket_hot.py --include-sports
./scripts/collect.sh                               # launchd 入口（同上，带 start/done 日志）
```

`--limit` 是排除体育前的抓取数，排除后实际事件数会少一些。概率取自盘口中间价（价差 > 0.1 时取最新报价），仅代表市场定价。

调度：默认每 3600 秒，模板 `deploy/launchd/agent.plist.tmpl`（在仓库根执行）：

```bash
make launchd module=pm-trending action=install                 # 每小时
make launchd module=pm-trending action=install interval=14400  # 每 4 小时
make launchd module=pm-trending action=status
make launchd module=pm-trending action=uninstall
```

电脑睡眠期间错过的运行不会补跑，唤醒后按间隔继续。

## 产物（均不入库）

| 路径 | 内容 |
|---|---|
| `reports/latest.md` | 中文报告：话题热度排行、热门事件、24h 预期变化最大的市场 |
| `data/snapshots/<UTC 时间戳>.json.gz` | 完整快照（事件摘要，约 50 KB/次） |
| `data/snapshots/<UTC 时间戳>.csv.gz` | 每个子市场一行，`pd.read_csv(...)` 可直接读 |
| `logs/launchd.out.log` / `launchd.err.log` | 定时任务日志 |
