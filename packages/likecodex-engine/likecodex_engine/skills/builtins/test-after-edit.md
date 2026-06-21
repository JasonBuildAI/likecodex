---
name: test-after-edit
description: Run tests after code changes
runAs: inline
---

When modifying code, always run the project's test suite with run_command before finishing.
Detect the test command from project files (package.json, Makefile, pyproject.toml, Cargo.toml).
