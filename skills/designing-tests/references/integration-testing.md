# Integration Testing Reference

## Scope Rule

Integration tests verify behavior **within one service boundary**. External services are mocked or stubbed. Internal infrastructure (DB, cache, message broker) uses real instances via testcontainers.

```
✅ handler → service → repository → real DB (testcontainer)
✅ service → cache (real Redis testcontainer) → downstream mock
❌ service A → service B → service C (cross-service — use contract tests instead)
```

## What to Use Real vs Mock

| Component | Use Real | Mock |
|-----------|----------|------|
| Database | ✓ (testcontainer) | |
| Cache (Redis) | ✓ (testcontainer) | |
| Message broker | ✓ (testcontainer) | |
| External HTTP API | | ✓ |
| Other internal services | | ✓ |
| Email / SMS providers | | ✓ |

## Test Design Focus

Integration tests cover **scenarios** (not all permutations). Design from user/business perspective:

```
Scenario: user completes registration
  Given: valid registration payload
  When: POST /register
  Then: user persisted in DB, welcome event published to queue

Scenario: duplicate email rejected
  Given: email already exists in DB
  When: POST /register with same email
  Then: 409 Conflict returned, no duplicate in DB
```

One test per meaningful scenario. Don't repeat edge cases already covered at unit level.

## Testcontainers Pattern

```python
# conftest.py
import pytest
from testcontainers.postgres import PostgresContainer

@pytest.fixture(scope="session")
def postgres():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url()

@pytest.fixture(scope="function")
def db_session(postgres):
    engine = create_engine(postgres)
    Base.metadata.create_all(engine)
    session = Session(engine)
    yield session
    session.close()
    Base.metadata.drop_all(engine)
```

```go
// Go
func TestMain(m *testing.M) {
    ctx := context.Background()
    pg, _ := testcontainers.GenericContainer(ctx, testcontainers.GenericContainerRequest{
        ContainerRequest: testcontainers.ContainerRequest{
            Image:        "postgres:16-alpine",
            ExposedPorts: []string{"5432/tcp"},
            Env:          map[string]string{"POSTGRES_PASSWORD": "test"},
            WaitingFor:   wait.ForListeningPort("5432/tcp"),
        },
        Started: true,
    })
    defer pg.Terminate(ctx)
    os.Exit(m.Run())
}
```

## Message Queue Testing

### Producer Test
Invoke the action, assert the message published matches the expected schema.

```python
def test_order_placed_publishes_event(db_session, mock_publisher):
    service = OrderService(repo=OrderRepository(db_session), publisher=mock_publisher)

    order = service.place_order(user_id="u1", items=[...])

    mock_publisher.publish.assert_called_once_with(
        topic="orders.placed",
        payload={"order_id": order.id, "user_id": "u1", "total": ANY}
    )
```

### Consumer Test
Call the consumer handler directly with a constructed message. Do not trigger from upstream.

```python
def test_payment_confirmed_handler_marks_order_paid(db_session):
    # Setup: create order in DB directly
    order = create_order_in_db(db_session, status="pending")

    # Act: call handler directly with a constructed message
    handler = PaymentConfirmedHandler(repo=OrderRepository(db_session))
    handler.handle(PaymentConfirmedEvent(order_id=order.id, amount=Decimal("100.00")))

    # Assert: side effect in DB
    updated = db_session.get(Order, order.id)
    assert updated.status == "paid"
```

## API Contract Testing

For HTTP services, test at the handler level with a real test server:

```python
def test_get_user_returns_expected_schema(client, db_session):
    user = insert_user(db_session, id="u1", name="Alice")

    response = client.get("/users/u1")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "u1"
    assert body["name"] == "Alice"
    assert "password" not in body  # contract: sensitive fields not exposed
```

Focus on:
- Response schema matches contract
- Status codes for each outcome (200, 201, 400, 404, 409)
- Fields that must/must not be present

## State Machine Integration Scenarios

For state machine scenarios, set the entity to the source state directly in DB, then trigger the action through the full stack:

```python
def test_ship_order_transitions_to_shipped(client, db_session):
    # Set state directly — don't go through payment flow
    order = insert_order(db_session, id="o1", status="paid")

    response = client.post(f"/orders/{order.id}/ship", json={"tracking": "TRK123"})

    assert response.status_code == 200
    db_order = db_session.get(Order, "o1")
    assert db_order.status == "shipped"
    assert db_order.tracking_number == "TRK123"
```

## Idempotency Testing

Idempotency testing verifies that performing the same operation multiple times produces the same outcome without unintended side effects. Must-test scenarios:

- **PUT / DELETE**: inherently required to be idempotent by HTTP semantics
- **POST with idempotency key**: same key submitted twice must not create duplicates
- **Message consumers**: at-least-once delivery means duplicates will arrive — consumers must handle them safely

### Pattern: Act → Assert → Act Again → Assert Same State

```python
class TestCancelOrder:
    def test_cancel_is_idempotent(self, client, db_session):
        order = insert_order(db_session, id="o1", status="pending")

        response1 = client.post("/orders/o1/cancel")
        assert response1.status_code == 200

        # Second call — same result, no error, no extra side effects
        response2 = client.post("/orders/o1/cancel")
        assert response2.status_code == 200

        # Assert: only one cancel event persisted
        events = db_session.query(OrderEvent).filter_by(order_id="o1", type="cancelled").all()
        assert len(events) == 1
```

Key assertions:
1. Second call does not return an error
2. Final state is identical to after the first call
3. Side effects (DB records, events published) are not duplicated

### POST + Idempotency Key

POST is not inherently idempotent. Use an idempotency key header to make it safe to retry:

```python
class TestCreateOrder:
    def test_same_idempotency_key_returns_same_order_without_duplicate(self, client, db_session):
        payload = {"user_id": "u1", "items": [{"sku": "A1", "qty": 2}]}
        headers = {"Idempotency-Key": "req-abc-123"}

        response1 = client.post("/orders", json=payload, headers=headers)
        assert response1.status_code == 201
        order_id = response1.json()["id"]

        # Retry with same key → same order, no duplicate created
        response2 = client.post("/orders", json=payload, headers=headers)
        assert response2.json()["id"] == order_id

        count = db_session.query(Order).filter_by(user_id="u1").count()
        assert count == 1

    def test_different_idempotency_keys_create_separate_orders(self, client, db_session):
        payload = {"user_id": "u1", "items": [{"sku": "A1", "qty": 2}]}

        r1 = client.post("/orders", json=payload, headers={"Idempotency-Key": "key-1"})
        r2 = client.post("/orders", json=payload, headers={"Idempotency-Key": "key-2"})

        assert r1.json()["id"] != r2.json()["id"]
        assert db_session.query(Order).filter_by(user_id="u1").count() == 2
```

### PUT Idempotency

Multiple identical PUT requests must produce the same resource state:

```python
class TestUpdateUserProfile:
    def test_put_is_idempotent(self, client, db_session):
        insert_user(db_session, id="u1", name="Alice")
        payload = {"name": "Alice Updated", "bio": "Developer"}

        response1 = client.put("/users/u1", json=payload)
        assert response1.status_code == 200

        response2 = client.put("/users/u1", json=payload)
        assert response2.status_code == 200
        assert response2.json() == response1.json()

        user = db_session.get(User, "u1")
        assert user.name == "Alice Updated"
```

### Message Consumer Idempotency

At-least-once delivery guarantees that the same message may arrive more than once. Consumers must not double-apply effects:

```python
class TestPaymentConfirmedHandler:
    def test_duplicate_message_does_not_double_apply(self, db_session):
        order = insert_order(db_session, status="pending")
        handler = PaymentConfirmedHandler(repo=OrderRepository(db_session))
        event = PaymentConfirmedEvent(order_id=order.id, amount=Decimal("100.00"))

        handler.handle(event)
        assert db_session.get(Order, order.id).status == "paid"

        # Duplicate delivery — must not re-process
        handler.handle(event)
        assert db_session.get(Order, order.id).status == "paid"

        # No duplicate payment record
        payments = db_session.query(Payment).filter_by(order_id=order.id).all()
        assert len(payments) == 1

    def test_duplicate_message_does_not_republish_downstream_event(self, db_session, mock_publisher):
        order = insert_order(db_session, status="pending")
        handler = PaymentConfirmedHandler(
            repo=OrderRepository(db_session),
            publisher=mock_publisher,
        )
        event = PaymentConfirmedEvent(order_id=order.id, amount=Decimal("100.00"))

        handler.handle(event)
        handler.handle(event)  # duplicate

        # Downstream event published exactly once
        assert mock_publisher.publish.call_count == 1

```

---

## Anti-Patterns

- **Cross-service integration tests** — test each service independently; use contract tests for inter-service boundaries
- **Too many scenario permutations** — edge cases belong in unit tests; integration tests cover meaningful scenarios
- **Using production external services** — always mock or use testcontainers
- **Shared DB state between tests** — each test must start with a clean state (use transactions or truncation)
- **Testing from upstream service** — construct the service input directly
