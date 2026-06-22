# QuantLib MCP

> **An AI-native Model Context Protocol (MCP) server for QuantLib**

QuantLib MCP enables AI assistants such as ChatGPT, Claude, Gemini, Cursor, and other MCP-compatible clients to interact directly with QuantLib. Instead of relying on memorized APIs, AI models can use QuantLib as a live computational engine for pricing financial instruments, constructing yield curves, calculating risk measures, searching documentation, and generating production-quality QuantLib code.

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

## Goals

The project aims to provide an AI interface that is:

* **Financially correct** – calculations are performed by QuantLib.
* **Transparent** – assumptions and conventions are explicit.
* **Workflow-oriented** – users describe financial problems, not low-level APIs.
* **Maintainable** – designed to evolve alongside QuantLib.
* **Extensible** – contributors can add tools, resources, and workflows with ease.

---

## Features

### Financial Instruments

* Fixed Rate Bonds
* Floating Rate Bonds
* Zero Coupon Bonds
* Vanilla Swaps
* Swaptions
* Caps and Floors
* European Options
* American Options
* Bermudan Options
* Futures
* FRAs
* *(More instruments planned.)*

### Market Objects

* Yield Curves
* Discount Curves
* Zero Curves
* OIS Curves
* Volatility Surfaces
* Calendars
* Day Count Conventions
* Schedules
* Quotes
* Interest Rate Indexes

### Analytics

* Net Present Value (NPV)
* Yield
* Duration
* Modified Duration
* Convexity
* Delta
* Gamma
* Vega
* Theta
* Rho
* DV01 / PV01

### Documentation

* Search QuantLib documentation
* Search examples
* Search pricing engines
* Discover classes and constructors
* Generate complete QuantLib examples

---

# Architecture

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

# Repository Structure

```text
quantlib-mcp/

├── server/
│   ├── tools/
│   ├── resources/
│   ├── wrappers/
│   ├── prompts/
│   ├── parser/
│   ├── object_store.py
│   └── main.py
│
├── docs/
│
├── examples/
│
├── tests/
│
├── README.md
├── CONTRIBUTING.md
├── ARCHITECTURE.md
├── DEVELOPER_GUIDE.md
├── ROADMAP.md
└── pyproject.toml
```

---

# Core Components

## MCP Tools

Tools perform financial operations such as:

* Constructing yield curves
* Pricing instruments
* Computing Greeks
* Calibrating models
* Managing QuantLib objects
* Searching documentation

Each tool performs a single, well-defined task.

---

## MCP Resources

Resources provide static information to AI assistants, including:

* QuantLib documentation
* Financial glossary
* Market conventions
* Pricing engine catalogue
* Example library

---

## MCP Prompts

Workflow-specific prompts guide AI models in solving financial problems correctly.

Examples include:

* Bond pricing
* Curve construction
* Swap valuation
* Option pricing
* Model calibration
* Risk analysis

---

## Object Store

QuantLib objects persist throughout a conversation and are referenced by identifiers rather than recreated repeatedly.

Examples:

```text
curve_001
bond_002
swap_015
engine_003
```

This improves efficiency and enables complex, multi-step workflows.

---

# Example Workflow

A user asks:

> *"Price a five-year EUR payer swap using a flat 2.5% discount curve."*

QuantLib MCP can:

1. Set the evaluation date.
2. Create the appropriate calendar.
3. Build payment schedules.
4. Construct the discount curve.
5. Create the floating-rate index.
6. Build the swap.
7. Select the pricing engine.
8. Calculate NPV, fair fixed rate, and DV01.
9. Explain the assumptions and results.

---

# Documentation Search

QuantLib MCP can search:

* Source code
* Public headers
* Doxygen comments
* Examples
* Unit tests
* Release notes

This enables AI assistants to retrieve authoritative information instead of relying on memorized APIs.

---

# Design Principles

* QuantLib is the source of truth.
* Financial correctness takes priority over convenience.
* Prefer reusable QuantLib objects.
* Expose financial concepts rather than implementation details.
* Keep tools composable and easy to test.
* Avoid hallucinated APIs and undocumented behavior.

---

# Roadmap

### Phase 1

* Core MCP server
* Object store
* Dates and calendars
* Yield curves
* Bonds
* Swaps
* European options

### Phase 2

* Documentation search
* Example generation
* Pricing engines
* Volatility surfaces
* Risk analytics

### Phase 3

* Calibration workflows
* Monte Carlo methods
* Heston, Hull–White, and SABR models
* Advanced market objects

### Phase 4

* Automatic API extraction from QuantLib
* Semantic documentation search
* Intelligent workflow planning
* AI-assisted financial engineering

See **ROADMAP.md** for the complete development plan.

---

# Contributing

Contributions are welcome.

Please read:

* **CONTRIBUTING.md**
* **DEVELOPER_GUIDE.md**
* **ARCHITECTURE.md**

before submitting pull requests.

---

# Vision

The long-term vision is to create an AI-native interface for QuantLib where users interact using financial language instead of low-level APIs.

Instead of asking:

> "How do I construct a `DiscountingSwapEngine`?"

Users should be able to ask:

> "Price this swap using OIS discounting."

QuantLib MCP translates that request into the appropriate QuantLib workflow while providing transparent explanations of the underlying financial models, assumptions, and calculations.

---

# License

This project is released under the same open-source spirit as QuantLib. Please refer to the QuantLib project for the library's licensing information.

---

# Acknowledgements

QuantLib MCP is built on the exceptional work of the QuantLib community and its creator, Luigi Ballabio. Their decades of work have established QuantLib as one of the world's leading open-source libraries for quantitative finance.
