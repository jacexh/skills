---
name: go-web-ddd-framework
description: "Use when building Go Web projects with DDD and Clean Architecture on the github.com/go-jimu/template ecosystem. Covers: project bootstrapping, layer isolation, Value Objects, Aggregate Roots, CQRS, Domain Events via Mediator, Unit of Work transactions, error/logging lifecycle, fx wiring, and testing strategy."
metadata:
  version: 0.3
---

# Go DDD Framework — Production Standards

Strict layer isolation + deterministic component wiring. Every decision below is a production constraint, not a suggestion.

## Bootstrap

```bash
go install golang.org/x/tools/cmd/gonew@latest
gonew github.com/go-jimu/template <your-module-path>
make tools      # Install Buf + ConnectRPC generators
buf generate    # Generate API contracts
mysql -u root -p < scripts/sql/init.sql
```

## Directory Structure

```text
cmd/
  main.go               # fx.App entry point
  client/               # Optional CLI entry
configs/
  default.yml
internal/
  business/
    <module>/
      domain/           # Pure business: Entities, VOs, Domain Services, Repo interfaces, Events
      application/
        command/        # Write handlers — orchestrate only, no business logic
        query/          # Read handlers — bypass domain, map directly to DTOs
        handler/        # Async event handlers
        dto.go          # Request/Response DTOs
        assembler.go    # DTO <-> Entity mapping
      infrastructure/   # Repo impls, DOs, DB converters
      module.go         # fx.Module — wiring & registration
  pkg/                  # Shared internals: DB, HTTP, Log, EventBus
pkg/
  gen/                  # Generated ConnectRPC/Protobuf code
proto/                  # *.proto API definitions
scripts/
  sql/init.sql
Makefile                # gen, build, test, tools
```

## Domain Core Patterns

### Aggregate Root

The aggregate root guards all invariants. External code NEVER touches sub-entities directly.

```go
// domain/user.go
type UserID string

type User struct {
    id     UserID
    email  Email        // Value Object
    status UserStatus
    events []DomainEvent
}

func NewUser(id UserID, email Email) (*User, error) {
    if id == "" {
        return nil, oops.Errorf("user id is required")
    }
    u := &User{id: id, email: email, status: StatusActive}
    u.raise(&UserRegistered{UserID: string(id), Email: string(email)})
    return u, nil
}

func (u *User) ChangeEmail(newEmail Email) error {
    if u.status != StatusActive {
        return oops.Errorf("cannot change email of inactive user")
    }
    u.email = newEmail
    u.raise(&UserEmailChanged{UserID: string(u.id), NewEmail: string(newEmail)})
    return nil
}

func (u *User) PopEvents() []DomainEvent {
    evts := u.events
    u.events = nil
    return evts
}

func (u *User) raise(e DomainEvent) { u.events = append(u.events, e) }
```

### Value Objects

Use VOs for domain concepts with no identity — they validate themselves and are immutable.

```go
// domain/email.go
type Email string

func NewEmail(raw string) (Email, error) {
    if !strings.Contains(raw, "@") {
        return "", oops.Errorf("invalid email: %s", raw)
    }
    return Email(strings.ToLower(raw)), nil
}

// domain/money.go
type Money struct {
    amount   int64  // store cents, never float
    currency string
}

func NewMoney(amount int64, currency string) (Money, error) {
    if amount < 0 {
        return Money{}, oops.Errorf("money amount cannot be negative")
    }
    return Money{amount: amount, currency: currency}, nil
}

func (m Money) Add(other Money) (Money, error) {
    if m.currency != other.currency {
        return Money{}, oops.Errorf("currency mismatch: %s vs %s", m.currency, other.currency)
    }
    return Money{amount: m.amount + other.amount, currency: m.currency}, nil
}
```

### Repository Interface

Defined in `domain/`, operates on Aggregate Roots ONLY.

```go
// domain/repository.go
type UserRepository interface {
    FindByID(ctx context.Context, id UserID) (*User, error)
    Save(ctx context.Context, user *User) error
    Delete(ctx context.Context, id UserID) error
}
```

### Domain Events

```go
// domain/events.go
type DomainEvent interface {
    EventName() string
}

type UserRegistered struct {
    UserID string
    Email  string
}
func (e *UserRegistered) EventName() string { return "user.registered" }

type UserEmailChanged struct {
    UserID   string
    NewEmail string
}
func (e *UserEmailChanged) EventName() string { return "user.email_changed" }
```

### Domain Services

Use only when a business operation spans multiple aggregates.

```go
// domain/transfer_service.go
type TransferService struct {
    accounts AccountRepository
}

func (s *TransferService) Transfer(ctx context.Context, fromID, toID AccountID, amount Money) error {
    from, err := s.accounts.FindByID(ctx, fromID)
    if err != nil {
        return oops.With("from_id", fromID).Wrap(err)
    }
    to, err := s.accounts.FindByID(ctx, toID)
    if err != nil {
        return oops.With("to_id", toID).Wrap(err)
    }
    if err := from.Debit(amount); err != nil {
        return err
    }
    if err := to.Credit(amount); err != nil {
        return err
    }
    // Save both within a single Unit of Work
    return s.accounts.SaveAll(ctx, from, to)
}
```

## CQRS

### Command Handler (Write Path)

`Controller -> application/command -> Domain/Aggregate -> Repository -> publish events`

```go
// application/command/register_user.go
type RegisterUserCommand struct {
    UserID string
    Email  string
}

type RegisterUserHandler struct {
    users    domain.UserRepository
    mediator mediator.Mediator
}

func (h *RegisterUserHandler) Handle(ctx context.Context, cmd RegisterUserCommand) error {
    email, err := domain.NewEmail(cmd.Email)
    if err != nil {
        return err
    }
    user, err := domain.NewUser(domain.UserID(cmd.UserID), email)
    if err != nil {
        return err
    }
    if err := h.users.Save(ctx, user); err != nil {
        return oops.With("user_id", cmd.UserID).Wrap(err)
    }
    for _, evt := range user.PopEvents() {
        h.mediator.Publish(ctx, evt)
    }
    return nil
}
```

### Query Handler (Read Path)

Bypasses domain layer entirely. Maps DB rows directly to DTOs.

```go
// application/query/get_user.go
type GetUserQuery struct {
    UserID string
}

type UserDTO struct {
    ID    string `json:"id"`
    Email string `json:"email"`
}

type GetUserHandler struct {
    db *sqlx.DB
}

func (h *GetUserHandler) Handle(ctx context.Context, q GetUserQuery) (*UserDTO, error) {
    var dto UserDTO
    err := h.db.GetContext(ctx, &dto, "SELECT id, email FROM users WHERE id = ?", q.UserID)
    if err != nil {
        return nil, oops.With("user_id", q.UserID).Wrap(err)
    }
    return &dto, nil
}
```

### Event Handler (Async Path)

`Mediator -> application/handler -> side effects (email, audit, projection...)`

```go
// application/handler/user_events.go
type UserEventHandler struct {
    mailer EmailService
}

func (h *UserEventHandler) OnUserRegistered(ctx context.Context, evt *domain.UserRegistered) error {
    return h.mailer.SendWelcome(ctx, evt.Email)
}
```

## Unit of Work — Transaction Boundary

Transactions belong in `application/command/`, not domain or infrastructure.

```go
// internal/pkg/db/uow.go
type UnitOfWork interface {
    Do(ctx context.Context, fn func(ctx context.Context) error) error
}

// application/command/transfer_funds.go
type TransferFundsHandler struct {
    uow     db.UnitOfWork
    service *domain.TransferService
}

func (h *TransferFundsHandler) Handle(ctx context.Context, cmd TransferFundsCommand) error {
    amount, err := domain.NewMoney(cmd.AmountCents, cmd.Currency)
    if err != nil {
        return err
    }
    return h.uow.Do(ctx, func(ctx context.Context) error {
        return h.service.Transfer(ctx, domain.AccountID(cmd.FromID), domain.AccountID(cmd.ToID), amount)
    })
}
```

## Error & Logging Lifecycle

| Layer | Action |
|---|---|
| Domain / Application | `return oops.With("key", val).Wrap(err)` — wrap with context, **never log** |
| Infrastructure | `return oops.With("query", sql).Wrap(err)` — wrap with context, **never log** |
| Edge (Interceptor/Controller) | Map to API error code, log **once** with `slog.Any("error", err)` |

```go
// internal/pkg/connectrpc/interceptor.go  (edge layer)
func (i *ErrorInterceptor) WrapUnary(next connect.UnaryFunc) connect.UnaryFunc {
    return func(ctx context.Context, req connect.AnyRequest) (connect.AnyResponse, error) {
        resp, err := next(ctx, req)
        if err != nil {
            slog.ErrorContext(ctx, "request failed", slog.Any("error", err))
            return nil, toConnectError(err)
        }
        return resp, nil
    }
}
```

## Wiring (uber-go/fx)

### Module-level wiring (`module.go`)

```go
var Module = fx.Module("user",
    fx.Provide(infrastructure.NewUserRepository),
    fx.Provide(command.NewRegisterUserHandler),
    fx.Provide(query.NewGetUserHandler),
    fx.Provide(handler.NewUserEventHandler),
    fx.Invoke(func(
        srv v1connect.UserServiceHandler,
        c connectrpc.Server,
        m mediator.Mediator,
        h *handler.UserEventHandler,
    ) {
        c.Register(v1connect.NewUserServiceHandler(srv))
        m.Subscribe(h.OnUserRegistered)
    }),
)
```

### App-level composition (`cmd/main.go`)

```go
func main() {
    fx.New(
        pkg.Module,          // DB, HTTP server, Mediator, Logger
        user.Module,
        order.Module,
        payment.Module,
    ).Run()
}
```

## Testing Strategy

| Layer | Approach | Use mocks? |
|---|---|---|
| Domain | Pure unit tests, no external deps | No |
| Application (Command/Query) | Unit tests, mock repositories & services | Yes |
| Infrastructure | Integration tests against real DB (testcontainers) | No |
| E2E | HTTP-level tests against running server | No |

```go
// Domain layer — pure, no mocks
func TestUser_ChangeEmail_InactiveUser(t *testing.T) {
    u, _ := domain.NewUser("u1", mustEmail("a@example.com"))
    u.Deactivate()
    err := u.ChangeEmail(mustEmail("b@example.com"))
    assert.ErrorContains(t, err, "inactive")
}

// Application layer — mock the repository
func TestRegisterUserHandler(t *testing.T) {
    repo := &mockUserRepo{}
    med := &mockMediator{}
    h := command.NewRegisterUserHandler(repo, med)

    err := h.Handle(ctx, command.RegisterUserCommand{UserID: "u1", Email: "a@b.com"})
    assert.NoError(t, err)
    assert.Len(t, repo.saved, 1)
    assert.Len(t, med.published, 1)
}
```

## Architectural Red Lines

### No persistence in Domain

```go
// WRONG — DB tag in domain entity
type User struct {
    ID    string `db:"id"`   // ❌
    Email string `db:"email"` // ❌
}

// CORRECT — pure domain entity; DB mapping is in infrastructure DO
type User struct {
    id    UserID
    email Email
}
```

### No leaky infrastructure objects from Repository

```go
// WRONG — returns infrastructure DO
func (r *Repo) FindByID(id string) (*UserDO, error) { ... } // ❌

// CORRECT — returns domain entity
func (r *Repo) FindByID(ctx context.Context, id domain.UserID) (*domain.User, error) { ... } // ✅
```

### No business logic in Application layer

```go
// WRONG — validation/logic in command handler
func (h *Handler) Handle(ctx context.Context, cmd RegisterCmd) error {
    if !strings.Contains(cmd.Email, "@") { ... } // ❌ belongs in domain VO
}

// CORRECT — delegate to domain
func (h *Handler) Handle(ctx context.Context, cmd RegisterCmd) error {
    email, err := domain.NewEmail(cmd.Email) // ✅ VO validates itself
    ...
}
```

### No cross-module synchronous calls

```go
// WRONG — order module directly calls user module
func (h *OrderHandler) Handle(ctx context.Context, cmd PlaceOrderCmd) error {
    user, _ := h.userService.FindUser(cmd.UserID) // ❌ synchronous coupling
}

// CORRECT — react to domain events asynchronously
func (h *OrderEventHandler) OnUserDeactivated(ctx context.Context, evt *userdomain.UserDeactivated) error {
    return h.orders.CancelAllForUser(ctx, evt.UserID) // ✅ event-driven
}
```

## Quality Checklist

- [ ] Directory structure matches the canonical layout
- [ ] Repositories handle Aggregate Roots only, never sub-entities
- [ ] All domain state changes happen via methods (no direct field assignment from outside)
- [ ] Value Objects validate themselves in their constructors
- [ ] Domain layer has zero imports from `infrastructure/` or external DB libraries
- [ ] Command handlers contain zero business logic — only orchestration
- [ ] Queries bypass domain layer and map directly to DTOs
- [ ] Transactions (Unit of Work) are managed in `application/command/`, not domain
- [ ] Domain Events are published via Mediator after successful persistence
- [ ] Errors are wrapped with `oops` at each layer; logged only once at the edge
- [ ] Cross-module side effects use Domain Events, not direct service calls
- [ ] fx Modules register all providers and invoke wiring in `module.go`
