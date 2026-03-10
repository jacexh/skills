# Unit Testing Reference

## Core Rules

- Test **one behavior** per test. If the test name contains "and", split it.
- Mock **all** external dependencies: repositories, external APIs, clocks, queues.
- Do **not** mock internal pure logic or value objects — test them directly.
- Tests must be deterministic: no random data, no real clocks, no real network.

## AAA Structure

```python
def test_order_apply_discount_reduces_total():
    # Arrange — set up state directly
    order = Order(items=[Item(price=Decimal("100.00"))])

    # Act — one action
    order.apply_discount(percent=10)

    # Assert — one logical outcome
    assert order.total() == Decimal("90.00")
```

Never combine multiple Act steps in one test.

## Test Naming

Pattern: `test_<unit>_<condition>_<expected_outcome>`

```
test_calculate_discount_with_zero_percent_returns_original_price
test_parse_date_with_invalid_format_raises_value_error
test_user_activate_when_already_active_raises_conflict_error
```

## What to Mock

| Mock | Don't Mock |
|------|------------|
| Repositories / DB access | Pure domain logic |
| External HTTP services | Value objects |
| Message queue publishers | Internal helpers |
| System clock / `datetime.now()` | Deterministic calculations |
| File system | In-process transformations |

## Test Doubles

Prefer the simplest double that works:

**Fake** — real working implementation, simplified. Prefer for repositories.
```python
class FakeUserRepository:
    def __init__(self):
        self._store: dict[str, User] = {}

    def save(self, user: User) -> None:
        self._store[user.id] = user

    def find_by_id(self, user_id: str) -> User | None:
        return self._store.get(user_id)
```

**Stub** — returns canned data, no interaction verification.
```python
mock_repo.find_by_id.return_value = User(id="1", name="Alice")
```

**Mock** — verifies that a specific call occurred. Use sparingly.
```python
mock_publisher.publish.assert_called_once_with(expected_event)
```

Avoid mocking what you own. If testing business logic, use fakes over mocks.

## Boundary Value Pattern

```python
@pytest.mark.parametrize("age,expected", [
    (17, False),   # below minimum
    (18, True),    # lower boundary
    (19, True),    # just inside
    (64, True),    # just inside upper
    (65, True),    # upper boundary
    (66, False),   # above maximum
])
def test_is_eligible_by_age(age, expected):
    assert is_eligible(age) == expected
```

## Equivalence Class Pattern

```python
@pytest.mark.parametrize("email,valid", [
    ("user@example.com", True),    # valid class
    ("user.name+tag@sub.io", True),# valid class variant
    ("not-an-email", False),       # missing @ — invalid format
    ("@nodomain.com", False),      # missing local part
    ("", False),                   # empty
    (None, False),                 # null
])
def test_validate_email(email, valid):
    assert validate_email(email) == valid
```

## Exception Testing

```python
def test_divide_by_zero_raises_value_error():
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide(10, 0)

def test_withdraw_insufficient_funds_raises_with_amount():
    account = Account(balance=Decimal("50.00"))
    with pytest.raises(InsufficientFundsError) as exc_info:
        account.withdraw(Decimal("100.00"))
    assert exc_info.value.shortfall == Decimal("50.00")
```

## Clock / Time Testing

Never call `datetime.now()` directly in business logic — inject or mock it.

```python
# Using freezegun
from freezegun import freeze_time

@freeze_time("2026-01-15 10:00:00")
def test_token_expires_after_one_hour():
    token = Token.create(ttl_seconds=3600)
    assert token.expires_at == datetime(2026, 1, 15, 11, 0, 0)
```

## Anti-Patterns

- **Testing implementation, not behavior** — test what the function does, not how
- **Multiple assertions on unrelated things** — split into focused tests
- **Mocking internal collaborators** — reveals implementation coupling
- **`time.sleep()` in tests** — use fake clocks instead
- **Shared mutable state between tests** — each test must be independent
- **Testing private methods** — if it needs testing, make it a separate unit

## Related

- For TDD rhythm (write test first): see `tdd` skill
- For pytest-specific patterns: see `references/python-pytest.md`
- For Go-specific patterns: see `references/go-testing.md`
