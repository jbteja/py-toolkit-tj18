# Python Scripts & Toolkit

| Property          | Value                          |
|-------------------|--------------------------------|
| Project ID        | tj18                           |
| Started           | 10th April 2026                |
| Domain            | Automation Scripts,  Dev Tools |
| Stack             | Python, Docker, Dev Containers |

## 🚀 Overview

A structured collection of reusable Python scripts designed for automation, system utilities, and everyday engineering tasks. This repo is built with a focus on modular configurations, isolated dependencies, and a portable Dev Container setup to ensure a consistent environment across any machine.

## 💡 Motivation

Useful scripts often end up scattered across different directories, making them difficult to retrieve when needed again. This leads to the "reinvention of the wheel."

**py-toolkit** solves this by providing a centralized, well-organized repository where frequently used scripts are stored, versioned, and easily accessible. Over time, this becomes a growing library of tools that can be shared across projects, saving time and effort.

## ✨ Features

- 📦 **Modular Scripts** - Each utility is self-contained and can be imported or used independently.
- 🐳 **Dev Container Ready** - Pre-configured environment for VS Code, ensuring "it works on any machine".
- 🧹 **Clean Code** - Configured with Ruff for fast linting and formatting.
- 📝 **Documentation-First** - Every script mostly includes metadata and clear instructions for use.

## 🏗️ Template Creation

The end goal is to design a "mature" starting point for Python projects, where it solves common headaches of initial project setup by providing pre-configured standards.

**Standardized**:

- `pyproject.toml`: Centralized configuration for dependencies, linting, and formatting.
- `.editorconfig`: Ensures consistent indentation and line endings across all IDEs.
- `.gitattributes`: Hardens the repo against CRLF/LF line-ending issues.
- `devcontainer`: An instant development environment, targeted for VS Code but adaptable to other IDEs.
- `logging`: A clean, filtered logging setup that can be easily imported into any script.
