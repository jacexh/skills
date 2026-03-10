# Python / pytest Reference

## Rules

- **Use classes** to group tests for the same unit/interface. Standalone `test_` functions are not allowed.
- **No async test functions.** All tests must be synchronous. Use sync HTTP clients and sync fixtures.

## Setup

```toml
# pyproject.toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = ["-v", "--tb=short", "--strict-markers"]
markers = [
    "unit: unit tests",
    "integration: integration tests",
    "e2e: end-to-end tests",
    "slow: slow tests",
]

[tool.coverage.run]
source = ["src"]
omit = ["*/tests/*", "*/migrations/*"]
```

```bash
pytest -m unit            # run only unit tests
pytest -m "not slow"      # skip slow tests
pytest --cov=src tests/   # with coverage
```

## Class Organization

Each class covers one unit (function, method, or endpoint). Group by scenario within the class.

```python
# ❌ Wrong — standalone test functions
def test_calculate_fee_zero():
    ...

def test_calculate_fee_at_threshold():
    ...

# ✅ Correct — grouped by unit
class TestCalculateFee:
    def test_zero_amount_returns_zero(self):
        assert calculate_fee(Decimal("0.00")) == Decimal("0.00")

    def test_below_threshold_returns_zero(self):
        assert calculate_fee(Decimal("99.99")) == Decimal("0.00")

    def test_at_threshold_applies_fee(self):
        assert calculate_fee(Decimal("100.00")) == Decimal("5.00")

    def test_above_threshold_applies_fee(self):
        assert calculate_fee(Decimal("200.00")) == Decimal("10.00")
```

## Fixtures

Define shared fixtures in `conftest.py` or as class-level setup fixtures:

```python
# conftest.py
import pytest

@pytest.fixture                    # function scope (default) — fresh per test
def sample_user():
    return User(id="u1", email="alice@example.com")

@pytest.fixture(scope="module")    # created once per module
def db_schema(postgres_url):
    engine = create_engine(postgres_url)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)

@pytest.fixture(scope="session")   # created once per test session
def postgres():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url()
```

Fixture scopes from narrowest to widest: `function` → `class` → `module` → `session`

### Class-level setup via fixture

Use an `autouse` fixture inside the class to share state across all methods:

```python
class TestUserService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_email = Mock(spec=EmailService)
        self.service = UserService(email_service=self.mock_email)

    def test_register_sends_welcome_email(self):
        self.service.register(email="alice@example.com", password="secret")
        self.mock_email.send_welcome.assert_called_once_with("alice@example.com")

    def test_register_returns_user_id(self):
        result = self.service.register(email="alice@example.com", password="secret")
        assert result.id is not None
```

## Parametrize

Apply `@pytest.mark.parametrize` to the test method inside a class:

```python
class TestCalculateFee:
    @pytest.mark.parametrize("amount,expected_fee", [
        (Decimal("0.00"),    Decimal("0.00")),   # zero — boundary
        (Decimal("0.01"),    Decimal("0.00")),   # just above zero
        (Decimal("99.99"),   Decimal("0.00")),   # just below threshold
        (Decimal("100.00"),  Decimal("5.00")),   # threshold — boundary
        (Decimal("100.01"),  Decimal("5.00")),   # just above threshold
        (Decimal("1000.00"), Decimal("50.00")),  # large value
    ])
    def test_returns_correct_fee(self, amount, expected_fee):
        assert calculate_fee(amount) == expected_fee


class TestOrderCanCancel:
    @pytest.mark.parametrize("status,can_cancel", [
        pytest.param("pending",   True,  id="pending-can-cancel"),
        pytest.param("paid",      False, id="paid-cannot-cancel"),
        pytest.param("shipped",   False, id="shipped-cannot-cancel"),
        pytest.param("cancelled", False, id="already-cancelled"),
    ])
    def test_by_status(self, status, can_cancel):
        order = Order(status=status)
        assert order.can_cancel() == can_cancel
```

## Mocking

```python
from unittest.mock import Mock, patch

class TestUserService:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.mock_email = Mock(spec=EmailService)
        self.service = UserService(email_service=self.mock_email)

    def test_register_sends_welcome_email(self):
        self.service.register(email="alice@example.com", password="secret")
        self.mock_email.send_welcome.assert_called_once_with("alice@example.com")

    def test_register_with_duplicate_email_raises_conflict(self):
        self.mock_email.send_welcome.side_effect = ConflictError("email exists")
        with pytest.raises(ConflictError):
            self.service.register(email="alice@example.com", password="secret")


class TestGetCurrentTime:
    def test_returns_formatted_time(self):
        with patch("myapp.utils.datetime") as mock_dt:
            mock_dt.now.return_value = datetime(2026, 1, 15, 10, 0, 0)
            result = get_current_time()
        assert result == datetime(2026, 1, 15, 10, 0, 0)


class TestServiceWithRetry:
    def test_retries_on_transient_error(self):
        mock_client = Mock()
        mock_client.call.side_effect = [
            ConnectionError("timeout"),
            ConnectionError("timeout"),
            {"result": "ok"},
        ]
        result = service_with_retry(mock_client)
        assert result == {"result": "ok"}
        assert mock_client.call.call_count == 3

    def test_raises_after_max_retries(self):
        mock_client = Mock()
        mock_client.call.side_effect = ConnectionError("timeout")
        with pytest.raises(ConnectionError):
            service_with_retry(mock_client)
```

## Time Control with freezegun

```python
from freezegun import freeze_time

class TestSessionExpiry:
    @freeze_time("2026-01-15 10:00:00")
    def test_expires_at_is_set_on_creation(self):
        session = Session.create(ttl_minutes=30)
        assert session.expires_at == datetime(2026, 1, 15, 10, 30, 0)

    def test_is_valid_before_expiry(self):
        with freeze_time("2026-01-15 10:00:00") as frozen_time:
            session = Session.create(ttl_minutes=30)

            frozen_time.move_to("2026-01-15 10:29:59")
            assert session.is_valid()

            frozen_time.move_to("2026-01-15 10:30:00")
            assert not session.is_valid()
```

## HTTP Testing (sync)

Use `TestClient` (FastAPI/Starlette) or `httpx.Client` — never async clients in tests.

```python
from fastapi.testclient import TestClient  # or starlette.testclient.TestClient
from myapp.main import app

class TestCreateUser:
    @pytest.fixture(autouse=True)
    def setup(self, db_session):
        self.client = TestClient(app)
        self.db = db_session

    def test_returns_201_with_valid_payload(self):
        response = self.client.post("/users", json={
            "email": "alice@example.com",
            "password": "Secret123!"
        })
        assert response.status_code == 201
        assert response.json()["email"] == "alice@example.com"

    def test_returns_409_for_duplicate_email(self):
        insert_user(self.db, email="alice@example.com")
        response = self.client.post("/users", json={
            "email": "alice@example.com",
            "password": "Secret123!"
        })
        assert response.status_code == 409

    def test_password_not_exposed_in_response(self):
        response = self.client.post("/users", json={
            "email": "bob@example.com",
            "password": "Secret123!"
        })
        assert "password" not in response.json()
```

## Testcontainers

```python
import pytest
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer

@pytest.fixture(scope="session")
def postgres_url():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg.get_connection_url()

@pytest.fixture(scope="session")
def redis_url():
    with RedisContainer("redis:7-alpine") as r:
        yield f"redis://{r.get_container_host_ip()}:{r.get_exposed_port(6379)}"
```

## Exception Assertions

```python
class TestAccountWithdraw:
    def test_raises_when_insufficient_funds(self):
        account = Account(balance=Decimal("50"))
        with pytest.raises(InsufficientFundsError):
            account.withdraw(Decimal("100"))

    def test_error_message_includes_shortfall(self):
        account = Account(balance=Decimal("50"))
        with pytest.raises(InsufficientFundsError) as exc_info:
            account.withdraw(Decimal("100"))
        assert exc_info.value.shortfall == Decimal("50")


class TestValidateAge:
    def test_negative_age_raises_with_message(self):
        with pytest.raises(ValueError, match=r"Age must be between \d+ and \d+"):
            validate_age(-1)

    def test_zero_age_raises(self):
        with pytest.raises(ValueError):
            validate_age(0)
```

## Project Structure

```
tests/
├── conftest.py                # shared fixtures (DB, client, containers)
├── unit/
│   ├── test_order.py          # class TestOrderCanCancel, class TestOrderTotal, ...
│   ├── test_user_service.py   # class TestUserServiceRegister, ...
│   └── test_pricing.py        # class TestCalculateFee, ...
├── integration/
│   ├── test_order_api.py      # class TestCreateOrder, class TestGetOrder, ...
│   ├── test_payment_handler.py
│   └── conftest.py            # DB session fixture
└── e2e/
    ├── test_checkout_flow.py
    └── conftest.py
```

One class per unit under test. One file per module or service being tested.

## Monkeypatch

Use `monkeypatch` to patch environment variables, module attributes, or object methods without leaving side effects:

```python
class TestGetDatabaseUrl:
    def test_uses_env_variable(self, monkeypatch):
        monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
        assert get_database_url() == "postgresql://localhost/test"

    def test_falls_back_to_default_when_unset(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        assert get_database_url() == "sqlite:///:memory:"

    def test_patches_module_attribute(self, monkeypatch):
        monkeypatch.setattr("myapp.config.DEBUG", True)
        assert is_debug_mode() is True
```

Prefer `monkeypatch` over `os.environ` mutation — it automatically restores original state after each test.

## Property-Based Testing (hypothesis)

For logic with large input spaces, use `hypothesis` to generate test cases automatically:

```python
from hypothesis import given, strategies as st

class TestReverseString:
    @given(st.text())
    def test_double_reverse_is_identity(self, s):
        assert reverse(reverse(s)) == s

    @given(st.text())
    def test_length_preserved(self, s):
        assert len(reverse(s)) == len(s)

class TestAddition:
    @given(st.integers(), st.integers())
    def test_is_commutative(self, a, b):
        assert add(a, b) == add(b, a)
```

Use hypothesis when: the function has mathematical properties (commutativity, idempotency, round-trip), or when the input space is too large to enumerate with parametrize.
