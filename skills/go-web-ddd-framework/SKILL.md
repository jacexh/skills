---
name: go-web-ddd-framework
description: "The authoritative development and architectural framework for Go Web projects built on Domain-Driven Design (DDD) and Clean Architecture principles. Its scope encompasses the entire lifecycle of the 'github.com/go-jimu/template' ecosystem and any modular Go backend requiring strict layer isolation. It acts as a decision engine for: (1) Bootstrapping via `gonew`, (2) Enforcing architectural red lines, (3) Standardizing error/logging lifecycles, (4) Implementing CQRS & Domain Events, (5) Managing Domain Core Patterns (Aggregates, Entities, Services), and (6) Orchestrating components via Fx."
metadata:
  version: 0.2
---

# Universal Go DDD Framework Specialist

This framework defines the production standards for building maintainable, scalable Go applications. It prioritizes strict layer isolation and deterministic component wiring.

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

## 📂 Project Directory Structure

Adhering to this full structure is critical for maintaining consistency:

```text
├── cmd/                # Application entry points (fx.App initialization)
│   ├── main.go         # Main server entry
│   └── client/         # Optional client/CLI entry
├── configs/            # Configuration files (default.yml)
├── internal/
│   ├── business/       # Bounded Contexts (Modular Monolith)
│   │   └── <module>/
│   │       ├── domain/         # Entities, Domain Services, Repo Interfaces, Events
│   │       ├── application/    # Use Case Orchestration
│   │       │   ├── command/    # Write handlers (DTO in/out, No logic)
│   │       │   ├── query/      # Read handlers (DTO out, Fast path)
│   │       │   ├── handler/    # Event handlers (Async side effects)
│   │       │   ├── dto.go      # Request/Response DTO definitions
│   │       │   └── assembler.go # DTO <-> Entity mapping
│   │       ├── infrastructure/ # Repository Impls, DOs, Converters
│   │       └── module.go       # fx.Module (Registration & Wiring)
│   └── pkg/            # Shared Framework Logic (DB, HTTP, Log, EventBus)
├── pkg/                # Publicly importable packages
│   └── gen/            # Generated code (ConnectRPC, Protobuf)
├── proto/              # API Definitions (*.proto)
├── scripts/            # SQL/Automation scripts (init.sql)
└── Makefile            # Standard Task Runner (gen, build, test, tools)
```

## 🧠 Domain Core Patterns

The `domain/` layer is the heart of the application. It MUST remain pure and focused on business rules.

### 1. Entities & Aggregate Roots
- **Aggregate Root**: The entry point for a cluster of associated objects. All external access to the aggregate must go through the Root.
- **Identity**: Entities MUST have a unique identity (e.g., `ID`).
- **Encapsulation**: Entities should encapsulate business logic. Use methods to change state (e.g., `user.ChangeEmail(newEmail)`) rather than exposing all fields.
- **Invariants**: Aggregate Roots are responsible for maintaining business invariants (consistency rules) within the aggregate boundary.

### 2. Domain Services
- **When to use**: Use a Domain Service when a business operation involves **multiple aggregates** or when a logic doesn't naturally belong to a single Entity.
- **Interface**: Defined in `domain/` if it represents a pure business contract.
- **State**: Domain Services are typically stateless.

### 3. Repository Interfaces
- **Definition**: Defined in `domain/` as a contract (e.g., `type UserRepository interface`).
- **Scope**: Repositories operate on **Aggregate Roots** ONLY. Do not create repositories for sub-entities.

## ⚡ CQRS & Domain Events

### 1. Command Path (Write)
- **Flow**: Controller -> Application (Command) -> **Domain Service/Aggregate Root** -> Repository (Save).
- **Requirement**: Command handlers MUST be located in `application/command/`.
- **Events**: Entities publish Domain Events (e.g., `UserRegistered`) via the `Mediator`.

### 2. Query Path (Read)
- **Flow**: Controller -> Application (Query) -> Infra (QueryRepository) -> DB.
- **Requirement**: Query handlers MUST be located in `application/query/`.
- **Optimization**: Queries can bypass the Domain layer and use a `QueryRepository` to map results directly to DTOs.

### 3. Event Path (Async)
- **Flow**: Domain Event -> Mediator -> Application (Event Handler) -> Application/Domain logic.
- **Requirement**: Event handlers MUST be located in `application/handler/`.

## 🚫 Architectural Red Lines (Prohibited Practices)

- **No Persistence in Domain**: Domain entities MUST NOT know about XORM/GORM or databases.
- **No Leaky DOs**: Repositories MUST return Domain Entities, never Infrastructure DOs.
- **No Logic in Application Layer**: Application handlers MUST NOT contain business rules/logic.
- **No Log Spamming**: Error logging ONLY at the edge layer (Controller/Interceptor).
- **No Mixed CQRS Responsibility**: Commands must never return query data. Queries must never modify state.
- **No Synchronous Coupling**: Use **Domain Events** for cross-module side effects.

## 🛡 Error & Logging Lifecycle

1.  **Lower Layers**: Catch errors, wrap with context using `oops.With().Wrap(err)`. Do NOT log.
2.  **Edge Layer (Interceptors/Controllers)**: Handle wrapped error, map to API codes, and log ONCE with stack trace/TraceID.
    - **Standardized Logging**: Print error ONLY here using `slog.Any("error", err)`.

## 🔌 Wiring (uber-go/fx)

```go
var Module = fx.Module("domain.name",
    fx.Provide(infrastructure.NewRepository),
    fx.Provide(application.NewApplication),
    fx.Provide(handler.NewEventHandler),
    fx.Invoke(func(srv v1connect.Handler, c connectrpc.Server, m mediator.Mediator, h *handler.EventHandler) {
        c.Register(v1connect.NewHandler(srv))
        m.Subscribe(h)
    }),
)
```

## 🛠 Quality Checklist
- [ ] **Full Structure**: Adheres to the top-level directory layout and `application` subdirectories.
- [ ] **Aggregate Integrity**: Repositories only handle Aggregate Roots.
- [ ] **Encapsulated Entities**: Logic is inside Entities, not just getters/setters.
- [ ] **Pure Domain**: No DB tags or external libraries in the domain layer.
- [ ] **Structured Logging**: All error logs use `slog.Any("error", err)`.
- [ ] **Edge Logging**: Error logs only exist at the outermost layer.
