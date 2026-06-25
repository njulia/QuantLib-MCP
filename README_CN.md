# QuantLib MCP

> **面向 QuantLib 的 AI 原生模型上下文协议 (MCP) 服务器**

QuantLib MCP 使 ChatGPT、Claude、Gemini、Cursor 及其他兼容 MCP 的 AI 助手能够直接与 QuantLib 交互。AI 模型无需依赖记忆中的 API，而是将 QuantLib 作为实时计算引擎来为金融工具定价、构建收益率曲线、计算风险指标以及生成生产级 QuantLib 代码。

[English](README.md) | [中文版](README_CN.md)

---

## 为什么需要 QuantLib MCP？

QuantLib 是量化金融领域的行业标准开源库，提供了金融工具、定价模型、收益率曲线、随机过程、校准例程和市场惯例的稳健实现。

然而，其庞大的 API 表面对 AI 助手来说是一个挑战：

* 数千个类和函数
* 复杂的对象依赖关系
* 众多定价引擎和市场惯例
* 跨版本的频繁 API 变更

QuantLib MCP 通过模型上下文协议 (MCP) 将 QuantLib 暴露给 AI 模型，使 AI 能够直接使用该库，而非猜测其行为。

---

## 安装

### 前置条件

- Python 3.10+
- QuantLib Python 绑定

```bash
pip install QuantLib
pip install mcp
```

---

## 快速开始

### 运行服务器

```bash
# 使用 server.py（主服务器）
python -m src.server.server

# 使用 server_llm.py（面向 LLM 的服务器）
python -m src.server.server_llm
```

### 从 MCP 客户端连接

配置您的 MCP 客户端连接到服务器端点。服务器暴露了用于金融工具定价和定量分析的工具。

---

## 可用工具

所有工具按类别组织在 `src/server/tools/` 目录下。

### 债券类 (`src/server/tools/bonds.py`)

| 工具 | 描述 |
|------|------|
| `price_fixed_rate_bond` | 固定利率债券定价，含久期、凸性和现金流分析 |
| `price_floating_rate_bond` | 使用 Ibor 指数定价浮动利率债券 |
| `price_zero_coupon_bond` | 零息债券定价 |
| `price_callable_bond` | 使用 Hull-White 单因子模型定价可赎回债券 |
| `price_cms_rate_bond` | CMS（固定息票互换）利率债券定价 |
| `price_inflation_linked_bond` | 通胀挂钩（CPI）债券定价 |
| `bond_cashflow_analysis` | 债券现金流分析，含现值和权重 |

### 互换类 (`src/server/tools/swaps.py`)

| 工具 | 描述 |
|------|------|
| `price_vanilla_swap` | 普通固定对浮动利率互换定价 |
| `price_float_float_swap` | 浮动对浮动利率互换定价 |
| `price_overnight_indexed_swap` | 隔夜指数互换 (OIS) 定价 |
| `price_zero_coupon_swap` | 零息互换定价 |
| `price_basis_swap` | 基差互换定价（不同 Ibor 期限） |
| `create_swap_schedule` | 生成互换付息计划 |

### 期权类 (`src/server/tools/options.py`)

| 工具 | 描述 |
|------|------|
| `price_european_option` | 使用 Black-Scholes-Merton 模型定价欧式期权 |
| `price_american_option` | 使用二叉树定价美式期权 (CRR, JR, EQP) |
| `price_bermudan_option` | 定价百慕大期权，支持多个行权日期 |
| `price_barrier_option` | 定价障碍期权（上/下、敲入/敲出） |
| `price_asian_option` | 定价亚式期权（算术/几何平均） |
| `price_binary_option` | 定价二元期权（现金或无价值） |
| `price_double_barrier_option` | 定价双障碍期权 |

### 波动率类 (`src/server/tools/volatility.py`)

| 工具 | 描述 |
|------|------|
| `price_cap` | 利率上限期权 (Cap) 定价 |
| `price_floor` | 利率下限期权 (Floor) 定价 |
| `price_cap_floor_strip` | Cap/Floor 条带定价 |
| `price_swaption` | 互换期权 (Swaption) 定价（欧式） |
| `price_swaption_volatility_surface` | 使用波动率曲面定价互换期权 |

### 信用类 (`src/server/tools/credit.py`)

| 工具 | 描述 |
|------|------|
| `price_credit_default_swap` | 信用违约互换 (CDS) 定价 |
| `price_cds_with_term_structure` | 使用风险率期限结构定价 CDS |
| `price_cds_option` | CDS 期权定价 |
| `calculate_cds_fair_spread` | 计算 CDS 公平利差 |

### 货币市场类 (`src/server/tools/money_market.py`)

| 工具 | 描述 |
|------|------|
| `price_fra` | 远期利率协议 (FRA) 定价 |
| `price_deposit` | 存款工具定价 |
| `price_futures` | 利率期货定价 |
| `build_deposit_futures_curve` | 使用存款和期货构建短期收益率曲线 |
| `calculate_forward_rate` | 计算远期利率 |

### 核心工具 (`src/server/server.py`)

| 工具 | 描述 |
|------|------|
| `price_european_option` | 欧式期权定价（遗留，在主服务器中） |
| `price_fixed_rate_bond` | 固定利率债券定价（遗留，在主服务器中） |
| `bootstrap_yield_curve` | 使用市场工具引导收益率曲线 |

---

## 架构

```text
                  AI 助手
         (ChatGPT / Claude / Cursor)

                    │
                    │  模型上下文协议
                    ▼
            ┌──────────────────────┐
            │    QuantLib MCP      │
            ├──────────────────────┤
            │ • 工具               │
            │ • 资源               │
            │ • 提示词             │
            │ • 对象存储           │
            └──────────────────────┘
                    │
                    ▼
             QuantLib Python API
                    │
                    ▼
              QuantLib C++ 库
```

---

## 仓库结构

```text
quantlib-mcp/
├── src/
│   ├── server/
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── bonds.py          # 债券类工具
│   │   │   ├── swaps.py          # 互换类工具
│   │   │   ├── options.py        # 期权类工具
│   │   │   ├── volatility.py     # Cap/Floor/Swaption
│   │   │   ├── credit.py         # CDS 和信用类工具
│   │   │   └── money_market.py   # FRA、存款、期货
│   │   ├── server.py             # 主 MCP 服务器
│   │   └── server_llm.py         # 面向 LLM 的服务器
│   └── client/
│       └── client.py             # MCP 客户端
├── prompts/
│   ├── workflows/                # 工作流提示词
│   └── documentation/            # 文档参考
├── README.md
├── README_CN.md
├── LICENSE
└── ...
```

---

## 使用示例

### 定价固定利率债券

```python
price_fixed_rate_bond(
    settlement_date="2026-06-25",
    maturity_date="2031-06-25",
    coupon_rate=0.05,
    yield_rate=0.045,
    frequency=2,
    face_value=100.0
)
```

### 定价普通互换

```python
price_vanilla_swap(
    settlement_date="2026-06-25",
    maturity_date="2031-06-25",
    fixed_rate=0.035,
    floating_spread=0.0,
    nominal=10_000_000.0,
    fixed_leg_frequency=1,
    floating_leg_frequency=2,
    yield_rate=0.04
)
```

### 定价欧式期权

```python
price_european_option(
    spot=100.0,
    strike=105.0,
    volatility=0.20,
    risk_free_rate=0.05,
    dividend_yield=0.02,
    maturity_date="2027-06-25",
    settlement_date="2026-06-25",
    option_type="call"
)
```

---

## 设计原则

* **QuantLib 是唯一的真相来源** - 所有计算均由 QuantLib 执行。
* **金融正确性优先**于便利性。
* **偏好可重用的 QuantLib 对象** - 对象通过标识符持久化。
* **暴露金融概念**而非实现细节。
* **保持工具可组合且易于测试**。
* **避免幻觉 API** 和未记录的行为。

---

## 贡献

欢迎贡献代码。提交 Pull Request 前请先阅读贡献指南。

---

## 许可证

本项目采用 MIT 许可证发布。详情请参阅 [LICENSE](LICENSE) 文件。

---

## 致谢

QuantLib MCP 建立在 QuantLib 社区及其创始人 Luigi Ballabio 的杰出工作之上。他们数十年的工作使 QuantLib 成为全球领先的量化金融开源库之一。
