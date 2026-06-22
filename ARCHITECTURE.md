# QuantLib MCP Architecture

## Overview

QuantLib MCP is organized into layers. Each layer has a single responsibility.

```text
LLM
 │
 ▼
Model Context Protocol
 │
 ▼
MCP Server
 │
 ├── Tools
 ├── Resources
 ├── Prompts
 ├── Object Store
 └── Documentation Index
 │
 ▼
QuantLib Python
 │
 ▼
QuantLib C++
```

---

# Components

## MCP Server

Coordinates requests between the LLM and QuantLib.

Responsibilities include:

* Tool registration
* Session management
* Object lifecycle
* Error handling
* Validation

---

## Tools

Tools execute operations.

Examples:

* Create yield curves
* Price instruments
* Calculate Greeks
* Build schedules
* Calibrate models

Tools should remain stateless.

---

## Resources

Resources provide read-only information.

Examples:

* Documentation
* Examples
* Market conventions
* Pricing engine catalog
* Financial glossary

---

## Prompts

Prompts define best practices for the LLM.

Examples:

* Bond pricing workflow
* Curve construction
* Option pricing
* Calibration workflow

---

## Object Store

QuantLib objects persist throughout a conversation.

Example:

```text
curve_001

bond_002

swap_004

engine_001
```

Objects are referenced by identifiers rather than recreated repeatedly.

---

## Wrapper Layer

The wrapper layer translates between MCP data models and QuantLib objects.

Responsibilities:

* Object creation
* Serialization
* Handle management
* Exception translation

---

## Documentation Index

The documentation index enables semantic search across:

* QuantLib headers
* Doxygen comments
* Examples
* Test suite
* Release notes

This reduces API hallucinations by allowing the LLM to retrieve authoritative information.

---

# Design Principles

* Separate financial workflows from implementation details.
* Keep tools small and composable.
* Prefer reusable QuantLib objects.
* Expose financial concepts rather than C++ internals.
* Preserve compatibility with future QuantLib releases.
