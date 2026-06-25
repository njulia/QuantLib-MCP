# QuantLib MCP

> **An AI-native Model Context Protocol (MCP) server for QuantLib**

QuantLib MCP enables AI assistants such as ChatGPT, Claude, Gemini, Cursor, and other MCP-compatible clients to interact directly with QuantLib. Instead of relying on memorized APIs, AI models can use QuantLib as a live computational engine for pricing financial instruments, constructing yield curves, calculating risk measures, and generating production-quality QuantLib code.

[中文版](README_CN.md) | [English](README.md)

---

## Why QuantLib MCP?

QuantLib is the industry-standard open-source library for quantitative finance. It provides robust implementations of financial instruments, pricing models, yield curves, stochastic processes, calibration routines, and market conventions.

However, its extensive API surface presents challenges for AI assistants:

* Thousands of classes and functions
* Complex object dependencies
* Numerous pricing engines and market conventions
* Frequent API evolution across releases

QuantLib MCP addresses these challenges by exposing QuantLib through the Model Context Protocol (MCP), enabling AI models to use the library directly instead of approximating its behavior.

---

## Installation

### Prerequisites

- Python 3.10+
- QuantLib Python bindings

```bash
pip install QuantLib
pip install mcp
```

---

## Quick Start

### Running the Server

```bash
# Using server.py (main server)
python -m src.server.server

# Using server_llm.py (LLM-oriented server)
python -m src.server.server_llm
```

### Connecting from an MCP Client

Configure your MCP client to connect to the server endpoint. The server exposes tools for pricing financial instruments and performing quantitative analysis.

---

## Available Tools

All tools are organized by category under `src/server/tools/`.

### Bonds (`src/server/tools/bonds.py`)

| Tool | Description |
|------|-------------|
| `price_fixed_rate_bond` | Price a fixed-rate bond with duration, convexity, and cashflow analysis |
| `price_floating_rate_bond` | Price a floating-rate bond using Ibor index |
| `price_zero_coupon_bond` | Price a zero-coupon bond |
| `price_callable_bond` | Price a callable bond using Hull-White one-factor model |
| `price_cms_rate_bond` | Price a CMS (Constant Maturity Swap) rate bond |
| `price_inflation_linked_bond` | Price an inflation-linked (CPI) bond |
| `bond_cashflow_analysis` | Analyze bond cashflows with present value and weights |

### Swaps (`src/server/tools/swaps.py`)

| Tool | Description |
|------|-------------|
| `price_vanilla_swap` | Price a vanilla fixed-vs-floating interest rate swap |
| `price_float_float_swap` | Price a floating-vs-floating rate swap |
| `price_overnight_indexed_swap` | Price an Overnight Indexed Swap (OIS) |
| `price_zero_coupon_swap` | Price a zero-coupon swap |
| `price_basis_swap` | Price a basis swap (different Ibor tenors) |
| `create_swap_schedule` | Generate swap payment schedules |

### Options (`src/server/tools/options.py`)

| Tool | Description |
|------|-------------|
| `price_european_option` | Price a European option using Black-Scholes-Merton model |
| `price_american_option` | Price an American option using binomial tree (CRR, JR, EQP) |
| `price_bermudan_option` | Price a Bermudan option with multiple exercise dates |
| `price_barrier_option` | Price a barrier option (Up/Down, In/Out) |
| `price_asian_option` | Price an Asian option (Arithmetic/Geometric average) |
| `price_binary_option` | Price a binary (cash-or-nothing) option |
| `price_double_barrier_option` | Price a double barrier option |

### Volatility (`src/server/tools/volatility.py`)

| Tool | Description |
|------|-------------|
| `price_cap` | Price an interest rate Cap |
| `price_floor` | Price an interest rate Floor |
| `price_cap_floor_strip` | Price Cap/Floor strips |
| `price_swaption` | Price a swaption (European) |
| `price_swaption_volatility_surface` | Price swaptions using a volatility surface |

### Credit (`src/server/tools/credit.py`)

| Tool | Description |
|------|-------------|
| `price_credit_default_swap` | Price a Credit Default Swap (CDS) |
| `price_cds_with_term_structure` | Price CDS using a hazard rate term structure |
| `price_cds_option` | Price a CDS option |
| `calculate_cds_fair_spread` | Calculate the fair spread for a CDS |

### Money Market (`src/server/tools/money_market.py`)

| Tool | Description |
|------|-------------|
| `price_fra` | Price a Forward Rate Agreement (FRA) |
| `price_deposit` | Price a deposit instrument |
| `price_futures` | Price an interest rate future |
| `build_deposit_futures_curve` | Build a short-end yield curve from deposits and futures |
| `calculate_forward_rate` | Calculate forward rates |

### Core Tools (`src/server/server.py`)

| Tool | Description |
|------|-------------|
| `price_european_option` | Price a European option (legacy, in main server) |
| `price_fixed_rate_bond` | Price a fixed-rate bond (legacy, in main server) |
| `bootstrap_yield_curve` | Bootstrap a yield curve from market helpers |

---

## Architecture

```text
                  AI Assistant
         (ChatGPT / Claude / Cursor)

                    │
                    │  Model Context Protocol
                    ▼
            ┌──────────────────────┐
            │    QuantLib MCP      │
            ├──────────────────────┤
            │ • Tools              │
            │ • Resources          │
            │ • Prompts            │
            │ • Object Store       │
            └──────────────────────┘
                    │
                    ▼
             QuantLib Python API
                    │
                    ▼
              QuantLib C++ Library
```

---

## Repository Structure

```text
quantlib-mcp/
├── src/
│   ├── server/
│   │   ├── tools/
│   │   │   ├── __init__.py
│   │   │   ├── bonds.py          # Bond instruments
│   │   │   ├── swaps.py          # Swap instruments
│   │   │   ├── options.py        # Option instruments
│   │   │   ├── volatility.py     # Cap/Floor/Swaption
│   │   │   ├── credit.py         # CDS and credit instruments
│   │   │   └── money_market.py   # FRA, Deposit, Futures
│   │   ├── server.py             # Main MCP server
│   │   └── server_llm.py         # LLM-oriented server
│   └── client/
│       └── client.py             # MCP client
├── prompts/
│   ├── workflows/                # Workflow-specific prompts
│   └── documentation/            # Documentation references
├── README.md
├── README_CN.md
├── LICENSE
└── ...
```

---

## Example Usage

### Pricing a Fixed-Rate Bond

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

### Pricing a Vanilla Swap

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

### Pricing a European Option

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

## Design Principles

* **QuantLib is the source of truth** - All calculations are performed by QuantLib.
* **Financial correctness** takes priority over convenience.
* **Prefer reusable QuantLib objects** - Objects persist via identifiers.
* **Expose financial concepts** rather than implementation details.
* **Keep tools composable and easy to test.**
* **Avoid hallucinated APIs** and undocumented behavior.

---

## Contributing

Contributions are welcome. Please read the contribution guidelines before submitting pull requests.

---

## License

This project is released under the MIT License. See [LICENSE](LICENSE) for details.

---

## Acknowledgements

QuantLib MCP is built on the exceptional work of the QuantLib community and its creator, Luigi Ballabio. Their decades of work have established QuantLib as one of the world's leading open-source libraries for quantitative finance.
