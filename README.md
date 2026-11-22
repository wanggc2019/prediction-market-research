# prediction-market-research

个人预测市场研究仓库。**一个仓库 = 若干自包含需求模块**，每个需求一个子目录（`pm-<需求>`），
模块之间不互相 import。

## 模块

| 目录 | 需求 | 运行时 | 说明 |
|---|---|---|---|
| [`pm-trending/`](pm-trending/README.md) | Polymarket 热点事件采集 → 话题热度 / 市场预期 / 预期变化报告 + 快照 | Python 3（标准库） | 2026-11-19 从仓库根迁入；Gamma API 只读、零 key，launchd 每小时 |

## 结构

```
prediction-market-research/
├── README.md / Makefile
├── tools/launchd.sh          # 按模块模板渲染/安装 launchd 任务
└── pm-<需求>/                 # 自包含模块
    ├── README.md
    ├── scripts/              # 代码；collect.sh 为定时入口
    ├── deploy/launchd/       # agent.plist.tmpl
    └── data/ reports/ logs/  # 运行产物（.gitignore）
```

launchd Label 统一为 `com.prediction-market-research.<模块名>`：

```bash
make launchd module=<模块> action=install|uninstall|status [interval=秒]
```

## Git 钩子

gitleaks 和 AI 代码审查用的是本机全局 git 钩子（`~/dotfiles`，`core.hooksPath=~/.config/git/hooks`），本仓库不单独配置。
本仓库不要设置 `core.hooksPath`，否则全局钩子不生效。
