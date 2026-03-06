---
name: go-web-ddd-framework
description: The authoritative development and architectural framework for Go Web projects built on Domain-Driven Design (DDD) and Clean Architecture principles. Its scope encompasses the entire lifecycle of the 'github.com/go-jimu/template' ecosystem and any modular Go backend requiring strict layer isolation (Domain, Infrastructure, Application). Use for project bootstrapping, directory structure management, cross-layer component orchestration with Fx, and implementing type-safe APIs with ConnectRPC.
metadata: 
  version: 0.1
---

# Universal Go DDD Framework Specialist

This skill provides a standardized workflow for building maintainable Go Web applications, optimized for the Jimu Template architecture and any project adhering to modern Clean Architecture standards.

## 📂 Project Directory Structure

Adhering to this structure is critical for maintaining layer isolation and modularity:

```
├── cmd/                # Application entry points (fx.App initialization)
├── configs/            # Configuration files (YAML/TOML)
├── internal/
│   ├── business/       # Business modules (Bounded Contexts)
│   │   └── <module>/   # Specific domain (e.g., 'user', 'order')
│   │       ├── domain/         # Pure Entities, Value Objects, Repository Interfaces
│   │       ├── application/    # Use Cases (Commands, Queries), DTO Assemblers
│   │       ├── infrastructure/ # DB/External implementations, DO Converters
│   │       └── module.go       # Module wiring (fx.Module)
│   └── pkg/            # Shared internal infrastructure (DB, HTTP, Log, Validator)
├── pkg/                # Public packages and generated code
│   └── gen/            # Generated Go code from Buf (ConnectRPC, Protobuf)
├── proto/              # Source Protocol Buffer definitions
├── scripts/            # SQL initialization, automation scripts
└── Makefile            # Build, test, and code generation commands
```

## 🚀 Bootstrap & Installation

1.  **Initialize Project**:
    ```bash
    go install golang.org/x/tools/cmd/gonew@latest
    gonew github.com/go-jimu/template <your-project-module-path>
    ```
2.  **Environment Setup**:
    ```bash
    make tools      # Install Buf and ConnectRPC generators
    buf generate    # Generate API contracts
    mysql -u root -p < scripts/sql/init.sql # Setup initial schema
    ```

## 🏗 Layered Architecture Standards

### 1. Domain Layer (`domain/`)
- **Entities**: Pure structs. No DB tags, no `context` in methods.
- **Repository Interface**: Define storage contracts here.
- **Mediator**: Use `mediator.Publish` for async/cross-module events.

### 2. Infrastructure Layer (`infrastructure/`)
- **DO (Data Objects)**: XORM/GORM structs with DB tags.
- **Repository**: Concrete implementations using internal database packages.
- **Converter**: Standardize `DOToEntity` and `EntityToDO` mappings.

### 3. Application Layer (`application/`)
- **CQS (Command/Query)**: Separate state-changing commands from read-only queries.
- **Assembler**: Map between `Domain Entity` and `API DTO/Proto`.
- **Application Service**: Orchestrate handlers and repositories.

## 🔌 The "Wiring" Pattern (uber-go/fx)

Each module MUST define an `fx.Module` for dependency injection:

```go
var Module = fx.Module(
        "domain.<module_name>",
        fx.Provide(infrastructure.NewRepository),
        fx.Provide(application.NewApplication),
        fx.Invoke(func(srv v1connect.APIHandler, c connectrpc.ConnectServer) {
                c.Register(v1connect.NewAPIHandler(srv))
        }),
)
```

## 🛠 Implementation Checklist

- [ ] **Error Handling**: Use `oops.With().Wrap(err)` for stack traces.
- [ ] **Logging**: Use `sloghelper.FromContext(ctx)` for trace IDs.
- [ ] **Transactions**: Utilize database context from `internal/pkg/database`.
- [ ] **Interface Check**: Use `var _ Interface = (*Implementation)(nil)`.

## 📈 Utility Commands
- `buf generate`: Refresh API code.
- `make unittest`: Run tests with race detection.
- `make server`: Start dev server with `configs/default.yml`.
