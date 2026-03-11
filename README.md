# Agent Skills

A collection of reusable AI agent skills — structured prompts and references that teach AI coding assistants how to apply best practices across languages and frameworks.

Each skill is a self-contained directory with a `SKILL.md` file. The skills work with any AI agent that supports custom instructions: **Gemini CLI**, **Claude Code**, **OpenAI Codex**, **Cursor**, **Windsurf**, and others.

## Repository Structure

- `skills/`: Individual skill directories. Each contains a `SKILL.md` (and optionally `scripts/`, `references/`, `assets/`).
- `resources/`: Shared assets and references used across multiple skills.

## Installation

### Gemini CLI

```bash
# Package a skill
node <path-to-gemini-cli-core>/dist/src/skills/builtin/skill-creator/scripts/package_skill.cjs skills/<skill-name>

# Install (user scope)
gemini skills install skills/<skill-name>.skill --scope user

# Or install all at once
for skill in skills/*/; do
  node <path-to-gemini-cli-core>/dist/src/skills/builtin/skill-creator/scripts/package_skill.cjs "$skill"
  gemini skills install "${skill%/}.skill" --scope user
done
```

### Claude Code

Claude Code has a native skills system that uses the same `SKILL.md` format as this repository. Skills live under `~/.claude/skills/` (global) or `.claude/skills/` (project-level) and are only loaded when invoked — they don't consume context on every session.

```bash
# Install a single skill
cp -r skills/<skill-name> ~/.claude/skills/

# Install all skills globally
cp -r skills/. ~/.claude/skills/

# Or symlink for live updates (edits to the repo reflect immediately)
ln -s "$(pwd)/skills/<skill-name>" ~/.claude/skills/<skill-name>
```

After installation, invoke any skill with `/<skill-name>` in Claude Code.

#### Claude Code Plugins

The following plugins from the Claude Code plugin marketplace should also be installed. They provide workflow skills (TDD, debugging, code review, etc.) that complement the domain skills in this repo.

| Plugin | Skills provided |
|---|---|
| `superpowers` | brainstorming, writing-plans, executing-plans, systematic-debugging, test-driven-development, verification-before-completion, requesting-code-review, receiving-code-review, finishing-a-development-branch, subagent-driven-development, dispatching-parallel-agents, using-git-worktrees, writing-skills, using-superpowers |
| `skill-creator` | skill-creator |
| `frontend-design` | frontend-design |

> These plugins overlap with skills in this repo. Install plugins first, then sync this repo — the install script will not overwrite plugin-provided skills.

### OpenAI Codex / Cursor / Windsurf

Paste the content of any `SKILL.md` into the tool's **system prompt**, **custom instructions**, or **rules** configuration. The YAML frontmatter block at the top (`---`) can be omitted if the tool doesn't support it.

### Creating a New Skill

1. Create a directory under `skills/<skill-name>/`.
2. Add a `SKILL.md` with a YAML frontmatter block (`name`, `description`) and the instruction content.
3. Optionally add `scripts/`, `references/`, or `assets/` subdirectories.

## Skills List

### Go
- [golang](skills/golang/SKILL.md): Build Go backend services with goroutines, channels, and idiomatic error handling.
- [golang-performance](skills/golang-performance/SKILL.md): Profile Go applications (pprof), run benchmarks, and optimize memory/CPU usage.
- [use-modern-go](skills/use-modern-go/SKILL.md): Apply modern Go syntax guidelines based on the project's Go version.
- [go-web-ddd-framework](skills/go-web-ddd-framework/SKILL.md): The authoritative development and architectural framework for Go Web projects built on Domain-Driven Design (DDD) and Clean Architecture principles.

### Python
- [async-python-patterns](skills/async-python-patterns/SKILL.md): Master Python asyncio, concurrent programming, and async/await patterns.
- [python-architecture](skills/python-architecture/SKILL.md): Python architecture patterns including KISS, SRP, separation of concerns, composition over inheritance, dependency injection, project structure, and module organization.
- [python-background-jobs](skills/python-background-jobs/SKILL.md): Python background job patterns including task queues and workers.
- [python-code-quality](skills/python-code-quality/SKILL.md): Python code quality including style, formatting, naming, docstrings, type safety, generics, protocols, and anti-pattern avoidance checklist.
- [python-configuration](skills/python-configuration/SKILL.md): Python configuration management via environment variables and typed settings.
- [python-observability](skills/python-observability/SKILL.md): Python observability patterns including logging, metrics, and tracing.
- [python-packaging](skills/python-packaging/SKILL.md): Create distributable Python packages with proper project structure.
- [python-performance-optimization](skills/python-performance-optimization/SKILL.md): Profile and optimize Python code using cProfile and performance best practices.
- [python-resource-management](skills/python-resource-management/SKILL.md): Python resource management with context managers and cleanup patterns.
- [python-robustness](skills/python-robustness/SKILL.md): Python robustness patterns including input validation, exception hierarchies, retry logic, timeouts, and fault-tolerant decorators.
- [uv-package-manager](skills/uv-package-manager/SKILL.md): Master the uv package manager for fast Python dependency management.

### Frontend
- [react-patterns](skills/react-patterns/SKILL.md): Modern React 19+ patterns including React Compiler, Server Actions, and new hooks.
- [react-typescript](skills/react-typescript/SKILL.md): Modern React 19+ patterns with TypeScript, TanStack Query, and Zod.
- [vue-typescript](skills/vue-typescript/SKILL.md): Vue 3 + TypeScript with Composition API, Pinia, and Vue Router.

### API & Database
- [api-design](skills/api-design/SKILL.md): Design REST/GraphQL APIs, including versioning, pagination, and documentation.
- [api-spec-analyzer](skills/api-spec-analyzer/SKILL.md): Analyze OpenAPI specs to provide TypeScript interfaces, request/response formats, and implementation guidance.
- [database-patterns](skills/database-patterns/SKILL.md): Database schema design, repository patterns, migrations, and query optimization.

### Workflow & Methodology
- [code-reviewer](skills/code-reviewer/SKILL.md): Senior code reviewer subagent — plan alignment, code quality, architecture, issue categorization.

### Testing
- [designing-tests](skills/designing-tests/SKILL.md): Language-agnostic test design strategy — layered pyramid (unit/integration/E2E), segmentation for microservice chains, state machines, and message queues, test case design techniques (equivalence partitioning, boundary value, decision table, idempotency). Includes references for Python/pytest and Go.
- [e2e-testing](skills/e2e-testing/SKILL.md): Playwright implementation reference for E2E tests — Page Object Model, auth state reuse, artifact management, CI/CD integration, and flaky test handling.

### General
- [system-design](skills/system-design/SKILL.md): Design systems from requirements using EventStorming, Mermaid diagrams, and progressive elaboration through 5 phases.
- [video-merger](skills/video-merger/SKILL.md): Merge multiple video files into a single output file using ffmpeg.

## Related Resources

- [Agent Skill Guide](https://agentskills.guide/)
- [Agent Skill](https://agentskills.io/)
- [Awesome Agent Skills](https://github.com/heilcheng/awesome-agent-skills)
- [superpowers](https://github.com/obra/superpowers)

## License

Apache License 2.0. See [LICENSE](LICENSE) for details.
