# prediction-market-research

## polymarket_hot.py — Polymarket 热点与市场预期

从 Polymarket 公开的 Gamma API（只读，不需要账号）抓取当前 24h 成交额最高的事件，生成：

- `reports/latest.md`：话题热度排行、热门事件及各选项概率、24h 预期变化最大的市场
- `data/snapshots/<时间戳>.json.gz|csv.gz`：完整快照，多次运行后可做时间序列分析

```bash
python3 polymarket_hot.py                  # 默认抓 100 个事件，排除体育/电竞
python3 polymarket_hot.py --limit 200 --top 30
python3 polymarket_hot.py --include-sports
```

只用 Python 标准库，无需安装依赖。概率取自盘口中间价，仅代表市场定价。

快照以 gzip 压缩保存（每次约 50 KB），`pd.read_csv("data/snapshots/xxx.csv.gz")` 可以直接读取。

### 定时采集（macOS）

```bash
bash scripts/install_schedule.sh              # 每小时运行一次（launchd），日志在 logs/
INTERVAL=14400 bash scripts/install_schedule.sh  # 改成每 4 小时一次
bash scripts/install_schedule.sh --uninstall  # 卸载
```
