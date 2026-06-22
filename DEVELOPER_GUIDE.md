# Developer Guide

This guide explains how to extend QuantLib MCP.

---

# Repository Layout

```text
server/
    tools/
    resources/
    wrappers/
    prompts/
    parser/
    models/
    object_store.py

tests/

docs/

examples/
```

---

# Adding a New Tool

A typical tool consists of:

1. Input model
2. Validation
3. QuantLib wrapper
4. Structured response
5. Tests
6. Documentation

Example workflow:

```text
LLM

↓

MCP Tool

↓

Wrapper

↓

QuantLib

↓

Structured Response
```

---

# Input Models

Use Pydantic for all request and response models.

Benefits:

* Validation
* Type safety
* Better error messages
* JSON schema generation

---

# Wrappers

Keep QuantLib-specific logic inside wrapper modules.

Avoid exposing QuantLib implementation details directly in tool definitions.

---

# Object Management

All reusable QuantLib objects should be stored in the session object store.

Examples:

* Curves
* Schedules
* Quotes
* Handles
* Pricing engines
* Instruments

Avoid recreating expensive objects.

---

# Error Handling

Translate QuantLib exceptions into clear, actionable messages.

Never expose raw C++ stack traces.

---

# Documentation

Every tool should include:

* Purpose
* Inputs
* Outputs
* Financial assumptions
* Example

---

# Testing

Every feature should include:

* Happy-path tests
* Invalid input tests
* Edge cases
* Financial regression tests

Whenever possible, compare results against QuantLib reference examples.

---

# Performance

Prefer:

* Reusing objects
* Lazy evaluation
* Relinkable handles
* Cached documentation indices

Avoid:

* Rebuilding curves unnecessarily
* Duplicate market data
* Repeated calibration

---

# Best Practices

* Think in financial workflows, not API calls.
* Keep tools focused and composable.
* Make assumptions explicit.
* Document market conventions.
* Validate all inputs.
* Use QuantLib as the authoritative calculation engine.

Following these principles will help keep QuantLib MCP reliable, maintainable, and useful for both developers and AI assistants.
