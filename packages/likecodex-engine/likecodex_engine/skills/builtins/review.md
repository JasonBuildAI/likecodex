---
name: review
description: Review code changes for bugs, style, and missing tests
runAs: subagent
---

Review the requested changes or files. Check for:
- Logic bugs and edge cases
- Missing error handling
- Test coverage gaps
- Style inconsistencies with surrounding code

Use git_diff when reviewing uncommitted changes. Provide actionable findings ranked by severity.
