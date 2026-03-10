# Adding a New Domain Module — Step-by-Step Guide

This guide walks through adding a complete new bounded context (e.g., `order`) to a go-jimu/template project. Replace `order`/`Order` with your actual module name throughout.

## Step 1: Define Proto API

Create `proto/order/v1/order_api.proto`:

```protobuf
syntax = "proto3";

package order.v1;

option go_package = "github.com/go-jimu/template/pkg/gen/order/v1;orderpb";

service OrderService {
  rpc Create(CreateOrderRequest) returns (CreateOrderResponse) {}
  rpc Get(GetOrderRequest) returns (GetOrderResponse) {}
  rpc List(ListOrdersRequest) returns (ListOrdersResponse) {}
}

message CreateOrderRequest {
  string user_id = 1;
  repeated OrderItem items = 2;
}

message OrderItem {
  string product_id = 1;
  int32 quantity = 2;
  int64 price_cents = 3;
}

message CreateOrderResponse {
  string id = 1;
}

message GetOrderRequest {
  string id = 1;
}

message GetOrderResponse {
  string id = 1;
  string user_id = 2;
  int64 total_cents = 3;
  string status = 4;
}

message ListOrdersRequest {
  string user_id = 1;
  int32 page = 2;
  int32 page_size = 3;
}

message ListOrdersResponse {
  int32 total = 1;
  repeated GetOrderResponse orders = 2;
}
```

Generate code:

```bash
buf generate
# Creates pkg/gen/order/v1/ with Go structs and ConnectRPC handler interface
```

## Step 2: Domain Layer

### 2a. Entity — `internal/business/order/domain/order.go`

```go
package domain

import (
    "time"

    "github.com/go-jimu/components/mediator"
    "github.com/go-jimu/template/internal/pkg/validator"
    "github.com/google/uuid"
)

// OrderStatus represents the lifecycle of an order.
type OrderStatus string

const (
    OrderStatusPending   OrderStatus = "pending"
    OrderStatusConfirmed OrderStatus = "confirmed"
    OrderStatusCancelled OrderStatus = "cancelled"
)

// Order is the aggregate root for the order bounded context.
type Order struct {
    ID        string      `validate:"required"`
    UserID    string      `validate:"required"`
    Status    OrderStatus `validate:"required"`
    Items     []OrderItem
    Events    mediator.EventCollection
    Version   int
    Deleted   bool
    CreatedAt time.Time
    UpdatedAt time.Time
}

// OrderItem is a value object within the Order aggregate.
type OrderItem struct {
    ProductID  string `validate:"required"`
    Quantity   int    `validate:"required,gt=0"`
    PriceCents int64  `validate:"required,gt=0"`
}

// NewOrder creates a new Order aggregate with validation.
func NewOrder(userID string, items []OrderItem) (*Order, error) {
    order := &Order{
        ID:     uuid.Must(uuid.NewV7()).String(),
        UserID: userID,
        Status: OrderStatusPending,
        Items:  items,
        Events: mediator.NewEventCollection(),
    }
    if err := order.Validate(); err != nil {
        return nil, err
    }
    order.Events.Add(EventOrderCreated{
        ID:     order.ID,
        UserID: userID,
        Total:  order.TotalCents(),
    })
    return order, nil
}

// TotalCents calculates the total price across all items.
func (o *Order) TotalCents() int64 {
    var total int64
    for _, item := range o.Items {
        total += item.PriceCents * int64(item.Quantity)
    }
    return total
}

// Confirm transitions the order to confirmed status.
func (o *Order) Confirm() error {
    if o.Status != OrderStatusPending {
        return oops.Errorf("cannot confirm order in status %s", o.Status)
    }
    o.Status = OrderStatusConfirmed
    o.Events.Add(EventOrderConfirmed{ID: o.ID})
    return nil
}

// Cancel transitions the order to cancelled status.
func (o *Order) Cancel() error {
    if o.Status == OrderStatusCancelled {
        return oops.Errorf("order already cancelled")
    }
    o.Status = OrderStatusCancelled
    o.Deleted = true
    return nil
}

// Validate validates the Order entity.
func (o *Order) Validate() error {
    return validator.Validate(o)
}
```

### 2b. Events — `internal/business/order/domain/event.go`

```go
package domain

import "github.com/go-jimu/components/mediator"

// EventOrderCreated is raised when a new order is created.
type EventOrderCreated struct {
    ID     string
    UserID string
    Total  int64
}

const EKOrderCreated = mediator.EventKind("order.created")

func (e EventOrderCreated) Kind() mediator.EventKind {
    return EKOrderCreated
}

// EventOrderConfirmed is raised when an order is confirmed.
type EventOrderConfirmed struct {
    ID string
}

const EKOrderConfirmed = mediator.EventKind("order.confirmed")

func (e EventOrderConfirmed) Kind() mediator.EventKind {
    return EKOrderConfirmed
}
```

### 2c. Repository Interface — `internal/business/order/domain/repository.go`

```go
package domain

import "context"

// Repository defines write-side persistence for the Order aggregate.
type Repository interface {
    Get(context.Context, string) (*Order, error)
    Save(context.Context, *Order) error
}
```

## Step 3: Application Layer

### 3a. DTOs — `internal/business/order/application/dto.go`

```go
package application

// Order is the read-side DTO.
type Order struct {
    ID         string `json:"id"`
    UserID     string `json:"user_id"`
    TotalCents int64  `json:"total_cents"`
    Status     string `json:"status"`
}

// CommandCreateOrder is the write-side command DTO.
type CommandCreateOrder struct {
    UserID string
    Items  []CommandOrderItem
}

type CommandOrderItem struct {
    ProductID  string
    Quantity   int
    PriceCents int64
}

// QueryListOrders is the read-side query request.
type QueryListOrders struct {
    UserID   string `form:"user_id"`
    Page     int    `form:"page"`
    PageSize int    `form:"page_size"`
}

type QueryListOrdersResponse struct {
    Total  int      `json:"total"`
    Orders []*Order `json:"orders"`
}
```

### 3b. Query Repository & Handler — `internal/business/order/application/query.go`

```go
package application

import (
    "context"
    "log/slog"

    "github.com/go-jimu/components/sloghelper"
)

// QueryRepository defines read-side data access.
type QueryRepository interface {
    FindOrders(ctx context.Context, userID string, limit, offset int) ([]*Order, error)
    CountOrders(ctx context.Context, userID string) (int, error)
}

// ListOrdersHandler handles order list queries.
type ListOrdersHandler struct {
    readModel QueryRepository
}

// NewListOrdersHandler creates a new ListOrdersHandler.
func NewListOrdersHandler(read QueryRepository) *ListOrdersHandler {
    return &ListOrdersHandler{readModel: read}
}

// Handle executes the list orders query.
func (h *ListOrdersHandler) Handle(ctx context.Context, logger *slog.Logger, req *QueryListOrders) (*QueryListOrdersResponse, error) {
    if req.PageSize == 0 {
        req.PageSize = 20
    }
    if req.PageSize > 100 {
        req.PageSize = 100
    }
    if req.Page == 0 {
        req.Page = 1
    }

    total, err := h.readModel.CountOrders(ctx, req.UserID)
    if err != nil {
        logger.ErrorContext(ctx, "failed to count orders", sloghelper.Error(err))
        return nil, err
    }

    offset := (req.Page - 1) * req.PageSize
    orders, err := h.readModel.FindOrders(ctx, req.UserID, req.PageSize, offset)
    if err != nil {
        logger.ErrorContext(ctx, "failed to find orders", sloghelper.Error(err))
        return nil, err
    }

    return &QueryListOrdersResponse{Total: total, Orders: orders}, nil
}
```

### 3c. Command Handler — `internal/business/order/application/command.go`

```go
package application

import (
    "context"
    "log/slog"

    "github.com/go-jimu/components/mediator"
    "github.com/go-jimu/components/sloghelper"
    "github.com/go-jimu/template/internal/business/order/domain"
)

// CreateOrderHandler handles order creation.
type CreateOrderHandler struct {
    repo domain.Repository
}

// NewCreateOrderHandler creates a new CreateOrderHandler.
func NewCreateOrderHandler(repo domain.Repository) *CreateOrderHandler {
    return &CreateOrderHandler{repo: repo}
}

// Handle creates a new order from the command.
func (h *CreateOrderHandler) Handle(ctx context.Context, logger *slog.Logger, cmd *CommandCreateOrder) (string, error) {
    // Convert command DTOs to domain value objects
    items := make([]domain.OrderItem, len(cmd.Items))
    for i, item := range cmd.Items {
        items[i] = domain.OrderItem{
            ProductID:  item.ProductID,
            Quantity:   item.Quantity,
            PriceCents: item.PriceCents,
        }
    }

    entity, err := domain.NewOrder(cmd.UserID, items)
    if err != nil {
        logger.ErrorContext(ctx, "failed to create order", sloghelper.Error(err))
        return "", err
    }

    if err = h.repo.Save(ctx, entity); err != nil {
        logger.ErrorContext(ctx, "failed to save order", sloghelper.Error(err))
        return "", err
    }

    entity.Events.Raise(mediator.Default())
    return entity.ID, nil
}
```

### 3d. Event Handler — `internal/business/order/application/handler.go`

```go
package application

import (
    "context"
    "log/slog"

    "github.com/go-jimu/components/mediator"
    "github.com/go-jimu/components/sloghelper"
    "github.com/go-jimu/template/internal/business/order/domain"
)

// OrderCreatedHandler handles side effects after order creation.
type OrderCreatedHandler struct{}

// NewOrderCreatedHandler creates a new handler.
func NewOrderCreatedHandler() *OrderCreatedHandler {
    return &OrderCreatedHandler{}
}

// Listening returns the event kinds this handler subscribes to.
func (h OrderCreatedHandler) Listening() []mediator.EventKind {
    return []mediator.EventKind{domain.EKOrderCreated}
}

// Handle processes the event (e.g., send notification, update inventory).
func (h OrderCreatedHandler) Handle(ctx context.Context, ev mediator.Event) {
    logger := sloghelper.FromContext(ctx)
    event, ok := ev.(domain.EventOrderCreated)
    if !ok {
        return
    }
    logger.Info("order created", slog.String("order_id", event.ID), slog.Int64("total", event.Total))
    // TODO: send notification, reserve inventory, etc.
}
```

### 3e. Assembler — `internal/business/order/application/assembler.go`

```go
package application

import (
    "github.com/go-jimu/template/internal/business/order/domain"
    orderv1 "github.com/go-jimu/template/pkg/gen/order/v1"
)

func assembleDomainOrder(entity *domain.Order) *orderv1.GetOrderResponse {
    return &orderv1.GetOrderResponse{
        Id:         entity.ID,
        UserId:     entity.UserID,
        TotalCents: entity.TotalCents(),
        Status:     string(entity.Status),
    }
}
```

### 3f. Application Service — `internal/business/order/application/application.go`

```go
package application

import (
    "context"
    "log/slog"

    "connectrpc.com/connect"
    "github.com/go-jimu/components/mediator"
    "github.com/go-jimu/components/sloghelper"
    "github.com/go-jimu/template/internal/business/order/domain"
    orderv1 "github.com/go-jimu/template/pkg/gen/order/v1"
    "github.com/go-jimu/template/pkg/gen/order/v1/orderv1connect"
)

// Queries groups read-side handlers.
type Queries struct {
    ListOrders *ListOrdersHandler
}

// Commands groups write-side handlers.
type Commands struct {
    CreateOrder *CreateOrderHandler
}

// Application is the order module's application service.
type Application struct {
    repo     domain.Repository
    Queries  *Queries
    Commands *Commands
    handlers []mediator.EventHandler
}

// NewApplication creates the application service, wires handlers, subscribes to events.
func NewApplication(ev mediator.Mediator, repo domain.Repository, read QueryRepository) orderv1connect.OrderServiceHandler {
    app := &Application{
        repo: repo,
        Queries: &Queries{
            ListOrders: NewListOrdersHandler(read),
        },
        Commands: &Commands{
            CreateOrder: NewCreateOrderHandler(repo),
        },
        handlers: []mediator.EventHandler{
            NewOrderCreatedHandler(),
        },
    }
    for _, hdl := range app.handlers {
        ev.Subscribe(hdl)
    }
    return app
}

// Create implements orderv1connect.OrderServiceHandler.
func (app *Application) Create(ctx context.Context, req *connect.Request[orderv1.CreateOrderRequest]) (*connect.Response[orderv1.CreateOrderResponse], error) {
    logger := sloghelper.FromContext(ctx).With(slog.String("user_id", req.Msg.GetUserId()))
    logger.Info("invoke Create method")

    cmd := &CommandCreateOrder{UserID: req.Msg.GetUserId()}
    for _, item := range req.Msg.GetItems() {
        cmd.Items = append(cmd.Items, CommandOrderItem{
            ProductID:  item.GetProductId(),
            Quantity:   int(item.GetQuantity()),
            PriceCents: item.GetPriceCents(),
        })
    }

    orderID, err := app.Commands.CreateOrder.Handle(ctx, logger, cmd)
    if err != nil {
        return nil, connect.NewError(connect.CodeInternal, err)
    }
    return connect.NewResponse(&orderv1.CreateOrderResponse{Id: orderID}), nil
}

// Get implements orderv1connect.OrderServiceHandler.
func (app *Application) Get(ctx context.Context, req *connect.Request[orderv1.GetOrderRequest]) (*connect.Response[orderv1.GetOrderResponse], error) {
    logger := sloghelper.FromContext(ctx).With(slog.String("order_id", req.Msg.GetId()))
    logger.Info("invoke Get method")

    entity, err := app.repo.Get(ctx, req.Msg.GetId())
    if err != nil {
        logger.Error("failed to get order", sloghelper.Error(err))
        return nil, connect.NewError(connect.CodeNotFound, err)
    }
    return connect.NewResponse(assembleDomainOrder(entity)), nil
}

// List implements orderv1connect.OrderServiceHandler.
func (app *Application) List(ctx context.Context, req *connect.Request[orderv1.ListOrdersRequest]) (*connect.Response[orderv1.ListOrdersResponse], error) {
    logger := sloghelper.FromContext(ctx).With(slog.String("user_id", req.Msg.GetUserId()))
    logger.Info("invoke List method")

    query := &QueryListOrders{
        UserID:   req.Msg.GetUserId(),
        Page:     int(req.Msg.GetPage()),
        PageSize: int(req.Msg.GetPageSize()),
    }

    result, err := app.Queries.ListOrders.Handle(ctx, logger, query)
    if err != nil {
        return nil, connect.NewError(connect.CodeInternal, err)
    }

    orders := make([]*orderv1.GetOrderResponse, len(result.Orders))
    for i, o := range result.Orders {
        orders[i] = &orderv1.GetOrderResponse{
            Id:         o.ID,
            UserId:     o.UserID,
            TotalCents: o.TotalCents,
            Status:     o.Status,
        }
    }
    return connect.NewResponse(&orderv1.ListOrdersResponse{
        Total:  int32(result.Total),
        Orders: orders,
    }), nil
}
```

## Step 4: Infrastructure Layer

### 4a. Data Object — `internal/business/order/infrastructure/do.go`

```go
package infrastructure

import "github.com/go-jimu/template/internal/pkg/database"

// OrderDO maps to the `order` database table.
type OrderDO struct {
    ID        string             `xorm:"id pk"`
    UserID    string             `xorm:"user_id"`
    Status    string             `xorm:"status"`
    Items     string             `xorm:"items"` // JSON serialized
    Version   int                `xorm:"version"`
    CreatedAt database.Timestamp `xorm:"created_at"`
    UpdatedAt database.Timestamp `xorm:"updated_at"`
    DeletedAt database.Timestamp `xorm:"deleted_at"`
}

// TableName returns the database table name.
func (o OrderDO) TableName() string {
    return "order"
}
```

### 4b. Converters — `internal/business/order/infrastructure/converter.go`

```go
package infrastructure

import (
    "encoding/json"
    "time"

    "github.com/go-jimu/components/mediator"
    "github.com/go-jimu/template/internal/business/order/application"
    "github.com/go-jimu/template/internal/business/order/domain"
    "github.com/go-jimu/template/internal/pkg/database"
    "github.com/samber/oops"
)

func convertOrderToDO(entity *domain.Order) (*OrderDO, error) {
    itemsJSON, err := json.Marshal(entity.Items)
    if err != nil {
        return nil, oops.Wrap(err)
    }
    do := &OrderDO{
        ID:        entity.ID,
        UserID:    entity.UserID,
        Status:    string(entity.Status),
        Items:     string(itemsJSON),
        Version:   entity.Version,
        UpdatedAt: database.NewTimestamp(time.Now()),
    }
    if entity.Deleted {
        do.DeletedAt = database.NewTimestamp(time.Now())
    } else {
        do.DeletedAt = database.NewTimestamp(database.UnixEpoch)
    }
    return do, nil
}

func convertOrderDO(do *OrderDO) (*domain.Order, error) {
    var items []domain.OrderItem
    if err := json.Unmarshal([]byte(do.Items), &items); err != nil {
        return nil, oops.Wrap(err)
    }
    entity := &domain.Order{
        ID:        do.ID,
        UserID:    do.UserID,
        Status:    domain.OrderStatus(do.Status),
        Items:     items,
        Events:    mediator.NewEventCollection(),
        Version:   do.Version,
        CreatedAt: do.CreatedAt.Time,
        UpdatedAt: do.UpdatedAt.Time,
    }
    if !do.DeletedAt.Time.IsZero() {
        entity.Deleted = true
    }
    return entity, nil
}

func convertOrderDOToDTO(do *OrderDO) *application.Order {
    return &application.Order{
        ID:         do.ID,
        UserID:     do.UserID,
        TotalCents: 0, // Calculated from items if needed
        Status:     do.Status,
    }
}
```

### 4c. Repository Implementation — `internal/business/order/infrastructure/order.go`

```go
package infrastructure

import (
    "context"
    "database/sql"
    "time"

    "github.com/go-jimu/components/mediator"
    "github.com/go-jimu/template/internal/business/order/application"
    "github.com/go-jimu/template/internal/business/order/domain"
    "github.com/go-jimu/template/internal/pkg/database"
    "github.com/samber/oops"
    "xorm.io/xorm"
)

type orderRepository struct {
    engine   *xorm.Engine
    mediator mediator.Mediator
}

type queryOrderRepository struct {
    engine *xorm.Engine
}

var (
    _ domain.Repository           = (*orderRepository)(nil)
    _ application.QueryRepository = (*queryOrderRepository)(nil)
)

// NewRepository creates the write-side repository.
func NewRepository(engine *xorm.Engine, mediator mediator.Mediator) domain.Repository {
    return &orderRepository{engine: engine, mediator: mediator}
}

// NewQueryRepository creates the read-side repository.
func NewQueryRepository(engine *xorm.Engine) application.QueryRepository {
    return &queryOrderRepository{engine: engine}
}

func (r *orderRepository) Get(ctx context.Context, id string) (*domain.Order, error) {
    do := new(OrderDO)
    has, err := r.engine.Context(ctx).Where("id = ? AND deleted_at = 0", id).Get(do)
    if err != nil {
        return nil, oops.With("order_id", id).Wrap(err)
    }
    if !has {
        return nil, oops.With("order_id", id).Wrap(sql.ErrNoRows)
    }
    return convertOrderDO(do)
}

func (r *orderRepository) Save(ctx context.Context, order *domain.Order) error {
    data, err := convertOrderToDO(order)
    if err != nil {
        return oops.With("order_id", order.ID).Wrap(err)
    }

    if order.Version == 0 {
        now := time.Now()
        data.CreatedAt = database.NewTimestamp(now)
        data.UpdatedAt = database.NewTimestamp(now)
        data.DeletedAt = database.NewTimestamp(database.UnixEpoch)
        affected, err := r.engine.Context(ctx).Insert(data)
        if err != nil {
            return oops.With("order_id", order.ID).Wrap(err)
        }
        if affected != 1 {
            return oops.With("order_id", order.ID).Wrap(sql.ErrNoRows)
        }
        return nil
    }

    data.UpdatedAt = database.NewTimestamp(time.Now())
    affected, err := r.engine.Context(ctx).
        Cols("status", "items", "updated_at", "deleted_at").
        Where("id = ? AND deleted_at = 0", order.ID).
        Update(data)
    if err != nil {
        return oops.With("order_id", order.ID).Wrap(err)
    }
    if affected == 0 {
        return oops.With("order_id", order.ID).Errorf("failed to save order")
    }
    return nil
}

func (q *queryOrderRepository) FindOrders(ctx context.Context, userID string, limit, offset int) ([]*application.Order, error) {
    dos := make([]*OrderDO, 0)
    err := q.engine.Context(ctx).
        Where("user_id = ? AND deleted_at = 0", userID).
        Limit(limit, offset).
        Desc("created_at").
        Find(&dos)
    if err != nil {
        return nil, oops.With("user_id", userID).Wrap(err)
    }

    dtos := make([]*application.Order, len(dos))
    for i, do := range dos {
        dtos[i] = convertOrderDOToDTO(do)
    }
    return dtos, nil
}

func (q *queryOrderRepository) CountOrders(ctx context.Context, userID string) (int, error) {
    count, err := q.engine.Context(ctx).
        Where("user_id = ? AND deleted_at = 0", userID).
        Count(new(OrderDO))
    if err != nil {
        return 0, oops.With("user_id", userID).Wrap(err)
    }
    return int(count), nil
}
```

## Step 5: fx Module Wiring

Create `internal/business/order/order.go`:

```go
package order

import (
    "connectrpc.com/connect"
    "github.com/go-jimu/template/internal/business/order/application"
    "github.com/go-jimu/template/internal/business/order/infrastructure"
    "github.com/go-jimu/template/internal/pkg/connectrpc"
    "github.com/go-jimu/template/pkg/gen/order/v1/orderv1connect"
    "go.uber.org/fx"
)

// Module is the fx module for the order bounded context.
var Module = fx.Module(
    "domain.order",
    fx.Provide(infrastructure.NewQueryRepository),
    fx.Provide(application.NewApplication),
    fx.Provide(infrastructure.NewRepository),
    fx.Invoke(func(srv orderv1connect.OrderServiceHandler, c connectrpc.ConnectServer) {
        c.Register(orderv1connect.NewOrderServiceHandler(
            srv,
            connect.WithInterceptors(c.GetGlobalInterceptors()...)))
    }),
)
```

## Step 6: Database Table

Add to `scripts/sql/init.sql`:

```sql
CREATE TABLE `order` (
  `id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(16) COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'pending',
  `items` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `version` smallint unsigned NOT NULL DEFAULT '0',
  `created_at` bigint unsigned NOT NULL DEFAULT '0',
  `updated_at` bigint unsigned NOT NULL DEFAULT '0',
  `deleted_at` bigint unsigned NOT NULL DEFAULT '0',
  PRIMARY KEY (`id`),
  KEY `idx_user_id` (`user_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

Key conventions:
- Timestamps stored as `bigint unsigned` (Unix milliseconds)
- Soft delete via `deleted_at` (0 = active, non-zero = deleted)
- UUID v7 string as primary key

## Step 7: Register in main.go

```go
// cmd/main.go
import (
    "github.com/go-jimu/template/internal/business/order"
    // ...existing imports
)

app := fx.New(
    fx.Provide(parseOption),
    fx.Provide(sloghelper.NewLog),
    fx.Provide(eventbus.NewMediator),
    pkg.Module,
    user.Module,
    order.Module,  // Add new module here
    fx.NopLogger,
)
```

## File Checklist

After completing all steps, verify these files exist:

```text
proto/order/v1/order_api.proto
pkg/gen/order/v1/                          (generated)
internal/business/order/
  domain/
    order.go                               (aggregate root)
    event.go                               (domain events)
    repository.go                          (repository interface)
  application/
    application.go                         (service + ConnectRPC handlers)
    command.go                             (write handlers)
    query.go                               (read handlers + QueryRepository)
    handler.go                             (event handlers)
    dto.go                                 (DTOs)
    assembler.go                           (domain -> proto)
  infrastructure/
    order.go                               (repository impls)
    do.go                                  (data objects)
    converter.go                           (entity <-> DO <-> DTO)
  order.go                                 (fx.Module)
scripts/sql/init.sql                       (updated with new table)
cmd/main.go                                (updated with order.Module)
```
