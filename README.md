# atour-search

亚朵酒店查询 Skill。无需登录，按城市和入住、离店日期，查询已开业门店的展示价、价格方案、开业时间和房型，用于协助规划行程。

本项目不是亚朵官方产品，查询到价格为 App 未登录时的展示价，会与登录后的会员价有一定差距。

## 让 Agent 安装

把下面这段发给 Agent：

```text
请安装这个 Skill。仓库是 https://github.com/BenjaminNH/atour-search-skill ，只安装其中的 atour-search 目录（里面有 SKILL.md），不要把整个仓库当作 Skill。
```

## 技术组成

- **语言**：Python 3.10+
- **依赖**：`requests`，见 [atour-search/scripts/requirements.txt](atour-search/scripts/requirements.txt)

## 许可

查询能力来自 [LIN-ZECHENG/Atour_Collection](https://github.com/LIN-ZECHENG/Atour_Collection)，MIT。许可见 [LICENSE](LICENSE)。使用前请阅读 [DISCLAIMER.md](DISCLAIMER.md)。
