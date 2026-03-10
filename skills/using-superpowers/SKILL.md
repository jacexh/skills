---
name: using-superpowers
description: Use when the user asks questions about how to use skills or when you need guidance on skill invocation priority
---

# Using Superpowers: Core Guidelines

This document establishes how to access and deploy skills—specialized workflows that override default behavior.

## Key Principle

"If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill." Skills take precedence over standard responses, including before clarifying questions.

## Access Method

Invoke the `Skill` tool in Claude Code to load relevant skill content, then follow it directly rather than reading skill files through other means.

## Priority Hierarchy

1. **User's explicit instructions** (highest)
2. **Superpowers skills** (override defaults)
3. **Default system prompt** (lowest)

User directives always control the process—if documentation says to skip a workflow, that instruction wins.

## Workflow Pattern

Check for applicable skills *before* taking action. Process skills (brainstorming, debugging) come before implementation skills. The document flags common rationalizations that signal you're avoiding the discipline requirement—phrases like "this is simple" or "I'll just check files first" suggest you need to stop and invoke a skill instead.

## Skill Categories

**Rigid skills** (like TDD) demand exact adherence. **Flexible skills** (like patterns) adapt to context. The skill itself indicates which applies.
