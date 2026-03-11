# Integration Testing Reference

## Test Naming

**Class**: `Test<Endpoint | Handler | Feature>` — one class per endpoint or handler under test.

**Method**: `test_<condition>_<expected_outcome>` — describes the scenario and what should happen.

```python
class TestCreateOrder:
    def test_valid_payload_returns_201_and_persists_order(self, client, db_session): ...
    def test_unauthenticated_request_returns_401(self, client): ...
    def test_duplicate_idempotency_key_returns_existing_order(self, client, db_session): ...
    def test_item_qty_zero_returns_400(self, client): ...

class TestPaymentConfirmedHandler:
    def test_pending_order_transitions_to_paid(self, db_session): ...
    def test_duplicate_message_does_not_double_apply(self, db_session): ...
    def test_already_paid_order_is_not_reprocessed(self, db_session): ...
```

Unlike unit test names (`test_<unit>_<condition>_<outcome>`), integration test names omit the unit prefix — the class already establishes the subject.

---

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

For idempotency test patterns (HTTP PUT/DELETE, POST + idempotency key, message consumer deduplication), see `references/idempotency-testing.md`.

## DB Test Isolation

Each integration test must start with a clean, predictable database state. Choose one strategy and apply it consistently within a test suite.

### Strategy Comparison

| Strategy | How it works | Pros | Cons |
|----------|-------------|------|------|
| **Transaction rollback** | Wrap each test in a transaction, rollback after | Fast, no cleanup needed | Cannot test code that manages its own transactions; implicit commit behavior hidden |
| **Truncation** | `TRUNCATE` all tables between tests | Works with any transaction pattern | Slower than rollback; must track table list |
| **Per-test database** | Create a fresh DB per test or test module | Full isolation, no interference | Slowest; only viable with testcontainers |

### Transaction Rollback (preferred for most cases)

```python
@pytest.fixture(scope="function")
def db_session(engine):
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()
```

```go
func setupTestTx(t *testing.T, db *sql.DB) *sql.Tx {
    tx, err := db.Begin()
    require.NoError(t, err)
    t.Cleanup(func() { tx.Rollback() })
    return tx
}
```

**When NOT to use rollback**: if the code under test calls `COMMIT` internally (e.g., saga steps, manual transaction management), rollback cannot undo committed changes — use truncation instead.

### Truncation

```python
@pytest.fixture(autouse=True)
def clean_db(db_session):
    yield
    for table in reversed(Base.metadata.sorted_tables):
        db_session.execute(table.delete())
    db_session.commit()
```

### Decision Rule

```
Does the code under test manage its own transactions (explicit commit)?
  → Yes: use truncation or per-test DB
  → No: use transaction rollback (fastest)
```

---

## Anti-Patterns

- **Cross-service integration tests** — test each service independently; use contract tests for inter-service boundaries
- **Too many scenario permutations** — edge cases belong in unit tests; integration tests cover meaningful scenarios
- **Using production external services** — always mock or use testcontainers
- **Shared DB state between tests** — each test must start with a clean state (see DB Test Isolation above)
- **Testing from upstream service** — construct the service input directly
