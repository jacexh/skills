# Go Testing Reference

## Setup

```bash
go test ./...                    # run all tests
go test ./... -v                 # verbose
go test ./... -run TestOrder     # filter by name
go test ./... -count=1           # disable test caching
go test -cover ./...             # coverage
go test -bench=. ./...           # benchmarks
```

Standard library `testing` + [testify](https://github.com/stretchr/testify) is the recommended combination.

```bash
go get github.com/stretchr/testify
go get github.com/testcontainers/testcontainers-go
```

## Table-Driven Tests

The idiomatic Go pattern for parametrized tests:

```go
func TestCalculateFee(t *testing.T) {
    cases := []struct {
        name     string
        amount   decimal.Decimal
        wantFee  decimal.Decimal
    }{
        {
            name:    "zero amount",
            amount:  decimal.NewFromFloat(0),
            wantFee: decimal.NewFromFloat(0),
        },
        {
            name:    "below threshold",
            amount:  decimal.NewFromFloat(99.99),
            wantFee: decimal.NewFromFloat(0),
        },
        {
            name:    "at threshold boundary",
            amount:  decimal.NewFromFloat(100.00),
            wantFee: decimal.NewFromFloat(5.00),
        },
        {
            name:    "above threshold",
            amount:  decimal.NewFromFloat(200.00),
            wantFee: decimal.NewFromFloat(10.00),
        },
    }

    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            got := CalculateFee(tc.amount)
            assert.Equal(t, tc.wantFee, got)
        })
    }
}
```

Use `t.Run()` always — it enables filtering and parallel sub-tests.

## Testify Assertions

```go
import (
    "github.com/stretchr/testify/assert"  // non-fatal (continues test)
    "github.com/stretchr/testify/require" // fatal (stops test immediately)
)

// Use require for preconditions, assert for post-conditions
func TestCreateOrder(t *testing.T) {
    order, err := NewOrder(items)
    require.NoError(t, err)           // stop if creation failed
    require.NotNil(t, order)

    assert.Equal(t, "pending", order.Status())
    assert.Equal(t, 3, order.ItemCount())
    assert.False(t, order.IsPaid())
}

// Error type assertion
func TestWithdrawInsufficientFunds(t *testing.T) {
    account := NewAccount(decimal.NewFromFloat(50))
    err := account.Withdraw(decimal.NewFromFloat(100))

    require.Error(t, err)
    assert.ErrorIs(t, err, ErrInsufficientFunds)
}
```

## Fakes for Repositories

```go
type FakeOrderRepository struct {
    orders map[string]*Order
}

func NewFakeOrderRepository() *FakeOrderRepository {
    return &FakeOrderRepository{orders: make(map[string]*Order)}
}

func (r *FakeOrderRepository) Save(ctx context.Context, o *Order) error {
    r.orders[o.ID()] = o
    return nil
}

func (r *FakeOrderRepository) FindByID(ctx context.Context, id string) (*Order, error) {
    o, ok := r.orders[id]
    if !ok {
        return nil, ErrNotFound
    }
    return o, nil
}

func TestPlaceOrder(t *testing.T) {
    repo := NewFakeOrderRepository()
    svc := NewOrderService(repo)

    order, err := svc.PlaceOrder(ctx, PlaceOrderCmd{UserID: "u1", Items: items})

    require.NoError(t, err)
    saved, _ := repo.FindByID(ctx, order.ID())
    assert.Equal(t, "pending", saved.Status())
}
```

## HTTP Handler Testing

```go
import "net/http/httptest"

func TestGetUserHandler(t *testing.T) {
    repo := NewFakeUserRepository()
    repo.Save(ctx, &User{ID: "u1", Name: "Alice"})

    handler := NewUserHandler(repo)
    router := setupRouter(handler)

    req := httptest.NewRequest(http.MethodGet, "/users/u1", nil)
    rec := httptest.NewRecorder()
    router.ServeHTTP(rec, req)

    assert.Equal(t, http.StatusOK, rec.Code)

    var body map[string]any
    require.NoError(t, json.NewDecoder(rec.Body).Decode(&body))
    assert.Equal(t, "u1", body["id"])
    assert.Equal(t, "Alice", body["name"])
    assert.NotContains(t, body, "password")
}
```

## Testcontainers (Integration)

```go
import (
    "github.com/testcontainers/testcontainers-go"
    "github.com/testcontainers/testcontainers-go/modules/postgres"
    "github.com/testcontainers/testcontainers-go/wait"
)

func TestMain(m *testing.M) {
    ctx := context.Background()

    pgContainer, err := postgres.RunContainer(ctx,
        testcontainers.WithImage("postgres:16-alpine"),
        postgres.WithDatabase("testdb"),
        postgres.WithUsername("test"),
        postgres.WithPassword("test"),
        testcontainers.WithWaitStrategy(
            wait.ForLog("database system is ready to accept connections").
                WithOccurrence(2),
        ),
    )
    if err != nil {
        log.Fatal(err)
    }
    defer pgContainer.Terminate(ctx)

    dsn, _ := pgContainer.ConnectionString(ctx, "sslmode=disable")
    db = setupDB(dsn)

    os.Exit(m.Run())
}
```

## Parallel Tests

```go
func TestOrderStatuses(t *testing.T) {
    t.Parallel()  // parallelize at top level

    cases := []struct{ name, status string }{
        {"pending", "pending"},
        {"paid", "paid"},
    }
    for _, tc := range cases {
        tc := tc  // capture range variable (Go < 1.22)
        t.Run(tc.name, func(t *testing.T) {
            t.Parallel()  // parallelize sub-tests
            // ...
        })
    }
}
```

Note: don't use `t.Parallel()` with shared mutable state or testcontainer sessions.

## State Machine Tests

```go
func TestOrderStateTransitions(t *testing.T) {
    cases := []struct {
        name        string
        fromStatus  OrderStatus
        action      func(*Order) error
        wantStatus  OrderStatus
        wantErr     error
    }{
        {
            name:       "pay pending order",
            fromStatus: StatusPending,
            action:     func(o *Order) error { return o.Pay() },
            wantStatus: StatusPaid,
        },
        {
            name:       "ship paid order",
            fromStatus: StatusPaid,
            action:     func(o *Order) error { return o.Ship("TRK123") },
            wantStatus: StatusShipped,
        },
        {
            name:       "cannot ship pending order",
            fromStatus: StatusPending,
            action:     func(o *Order) error { return o.Ship("TRK123") },
            wantErr:    ErrInvalidTransition,
        },
    }

    for _, tc := range cases {
        t.Run(tc.name, func(t *testing.T) {
            // Set state directly — don't traverse from initial
            order := OrderWithStatus(tc.fromStatus)

            err := tc.action(order)

            if tc.wantErr != nil {
                assert.ErrorIs(t, err, tc.wantErr)
                return
            }
            require.NoError(t, err)
            assert.Equal(t, tc.wantStatus, order.Status())
        })
    }
}
```

## Testify Mock (for external dependencies)

```go
import "github.com/stretchr/testify/mock"

type MockEmailService struct {
    mock.Mock
}

func (m *MockEmailService) SendWelcome(email string) error {
    args := m.Called(email)
    return args.Error(0)
}

func TestRegisterSendsWelcomeEmail(t *testing.T) {
    mockEmail := new(MockEmailService)
    mockEmail.On("SendWelcome", "alice@example.com").Return(nil)

    svc := NewUserService(mockEmail)
    err := svc.Register(ctx, "alice@example.com", "password")

    require.NoError(t, err)
    mockEmail.AssertExpectations(t)
}
```

## Project Structure

```
project/
├── internal/
│   ├── domain/
│   │   ├── order.go
│   │   └── order_test.go        # unit tests alongside source
│   └── service/
│       ├── order_service.go
│       └── order_service_test.go
└── tests/
    ├── integration/
    │   ├── main_test.go          # TestMain with testcontainers
    │   └── order_api_test.go
    └── e2e/
        └── checkout_test.go
```

Unit tests live next to source files (`_test.go`). Integration and E2E tests in a separate `tests/` directory to allow different build tags or run configurations.

## Build Tags for Test Separation

```go
//go:build integration

package integration_test
```

```bash
go test -tags integration ./tests/integration/...
go test -tags e2e ./tests/e2e/...
go test ./internal/...  # unit tests only (no build tags)
```
