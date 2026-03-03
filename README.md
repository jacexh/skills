# Agent Skills Repository

This repository is a collection of Agent Skills for Gemini CLI.

## Repository Structure

- `skills/`: Individual skill directories. Each contains a `SKILL.md` file.
- `resources/`: Shared assets, templates, and references used across multiple skills.
- `.gitignore`: Configured to ignore common noise and `.skill` packages.

## How to Create a New Skill

1.  Use the `init_skill.cjs` script to scaffold a new skill:
    ```bash
    # Ensure you have the path to gemini-cli-core/dist/src/skills/builtin/skill-creator/scripts/
    node <path-to-skill-creator>/init_skill.cjs <skill-name> --path skills/
    ```
2.  Edit the `SKILL.md` and add resources to `scripts/`, `references/`, or `assets/`.
3.  Package the skill:
    ```bash
    node <path-to-skill-creator>/package_skill.cjs skills/<skill-name>
    ```
4.  Install the skill:
    ```bash
    gemini skills install skills/<skill-name>.skill --scope workspace
    ```

## Skills List

### Go
- [use-modern-go](skills/use-modern-go/SKILL.md): Apply modern Go syntax guidelines based on the project's Go version.

### Python
- [async-python-patterns](skills/async-python-patterns/SKILL.md): Master Python asyncio, concurrent programming, and async/await patterns.
- [python-anti-patterns](skills/python-anti-patterns/SKILL.md): Common Python anti-patterns to avoid.
- [python-background-jobs](skills/python-background-jobs/SKILL.md): Python background job patterns including task queues and workers.
- [python-code-style](skills/python-code-style/SKILL.md): Python code style, linting, formatting, and documentation standards.
- [python-configuration](skills/python-configuration/SKILL.md): Python configuration management via environment variables and typed settings.
- [python-design-patterns](skills/python-design-patterns/SKILL.md): Python design patterns including KISS, SoC, and SRP.
- [python-error-handling](skills/python-error-handling/SKILL.md): Python error handling patterns and exception hierarchies.
- [python-observability](skills/python-observability/SKILL.md): Python observability patterns including logging, metrics, and tracing.
- [python-packaging](skills/python-packaging/SKILL.md): Create distributable Python packages with proper project structure.
- [python-performance-optimization](skills/python-performance-optimization/SKILL.md): Profile and optimize Python code using cProfile and performance best practices.
- [python-project-structure](skills/python-project-structure/SKILL.md): Python project organization, module architecture, and public API design.
- [python-resilience](skills/python-resilience/SKILL.md): Python resilience patterns including retries, backoff, and timeouts.
- [python-resource-management](skills/python-resource-management/SKILL.md): Python resource management with context managers and cleanup patterns.
- [python-testing-patterns](skills/python-testing-patterns/SKILL.md): Implement comprehensive testing strategies with pytest and fixtures.
- [python-type-safety](skills/python-type-safety/SKILL.md): Python type safety with type hints, generics, protocols, and strict checking.
- [uv-package-manager](skills/uv-package-manager/SKILL.md): Master the uv package manager for fast Python dependency management.

## License

This repository is licensed under the Apache License 2.0. See [LICENSE](LICENSE) for details.
