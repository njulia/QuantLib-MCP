# Contributing to QuantLib MCP

Thank you for your interest in contributing to QuantLib MCP.

Our goal is to build the best AI interface for QuantLib while maintaining high standards for financial correctness, software quality, and documentation.

---

# Guiding Principles

Every contribution should strive to improve one or more of the following:

* Financial correctness
* QuantLib compatibility
* AI usability
* Documentation quality
* Performance
* Test coverage
* Developer experience

Accuracy is more important than adding new features.

---

# Types of Contributions

We welcome contributions including:

* New MCP tools
* Documentation improvements
* Bug fixes
* Performance improvements
* Additional QuantLib wrappers
* New financial workflows
* Unit tests
* Integration tests
* Example notebooks
* Tutorials

---

# Development Workflow

1. Fork the repository.
2. Create a feature branch.
3. Implement your changes.
4. Add or update tests.
5. Run the complete test suite.
6. Update documentation if required.
7. Submit a Pull Request.

---

# Coding Standards

## Python

* Follow PEP 8.
* Use type hints.
* Use Pydantic models for tool inputs and outputs.
* Prefer composition over inheritance.
* Keep functions focused and testable.

---

## MCP Tools

Each tool should:

* Perform one well-defined task.
* Validate all inputs.
* Return structured output.
* Provide clear error messages.
* Avoid hidden assumptions.

---

## Financial Conventions

Never hard-code conventions.

Always specify:

* Calendar
* Day-count convention
* Business-day convention
* Settlement lag
* Compounding
* Payment frequency

---

# Testing

Every new feature should include:

* Unit tests
* Financial regression tests where appropriate
* Error handling tests

Whenever possible, compare results against published QuantLib examples.

---

# Documentation

Every public tool should include:

* Description
* Parameters
* Return values
* Financial assumptions
* Example usage

---

# Pull Requests

A good pull request should:

* Focus on a single feature or fix
* Include tests
* Include documentation updates
* Explain the motivation
* Describe any financial assumptions

---

# Code Review

Reviews focus on:

* Financial correctness
* API consistency
* Performance
* Maintainability
* Documentation
* Test coverage

---

# Questions

If you are unsure how to implement a feature, open a GitHub Discussion or Issue before starting significant work.
