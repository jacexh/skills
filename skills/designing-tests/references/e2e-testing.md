# E2E Testing Reference

## Scope Rule

E2E tests run against the **full real system** — no mocks, no stubs. They verify that critical user journeys work end-to-end.

Keep the E2E suite minimal. A bloated E2E suite is slow, flaky, and expensive to maintain. If a scenario can be covered at integration level, cover it there.

**Good E2E candidates:**
- User registration and first login
- Core purchase / checkout flow
- Critical data submission that crosses multiple services

**Not good E2E candidates:**
- Error messages for invalid input (unit test this)
- Every permutation of a form (integration test this)
- Admin / internal flows with low traffic

## One Test Per Critical Flow

Write one E2E test per user journey, covering the happy path. Variations and error paths belong in unit or integration tests.

```
✅ test_user_can_register_and_login
✅ test_user_can_complete_checkout
❌ test_user_cannot_register_with_invalid_email  ← unit test
❌ test_checkout_fails_when_card_declined        ← integration test
```

## Page Object Model

Encapsulate page interactions in Page Objects to keep tests readable and maintainable.

```python
class LoginPage:
    def __init__(self, page):
        self.page = page
        self.email = page.get_by_label("Email")
        self.password = page.get_by_label("Password")
        self.submit = page.get_by_role("button", name="Sign in")

    def login(self, email: str, password: str) -> "DashboardPage":
        self.email.fill(email)
        self.password.fill(password)
        self.submit.click()
        return DashboardPage(self.page)


class DashboardPage:
    def __init__(self, page):
        self.page = page
        self.welcome = page.get_by_text("Welcome")

    def is_loaded(self) -> bool:
        return self.welcome.is_visible()


def test_user_can_login(page):
    login_page = LoginPage(page)
    dashboard = login_page.login("alice@example.com", "password123")
    assert dashboard.is_loaded()
```

## Selector Strategy

Prefer selectors that survive UI changes:

| Priority | Selector | Example |
|----------|----------|---------|
| 1st | `data-testid` attribute | `page.get_by_test_id("submit-btn")` |
| 2nd | ARIA role + name | `page.get_by_role("button", name="Submit")` |
| 3rd | Label text | `page.get_by_label("Email address")` |
| 4th | Visible text | `page.get_by_text("Sign in")` |
| Avoid | CSS class / XPath | `page.locator(".btn-primary")` |

## Test Data Isolation

Each test must create its own data and not depend on data from other tests.

```python
@pytest.fixture
def registered_user(api_client):
    """Create a fresh user for this test only."""
    user = api_client.post("/users", json={
        "email": f"test_{uuid4()}@example.com",
        "password": "Test1234!"
    }).json()
    yield user
    api_client.delete(f"/users/{user['id']}")  # cleanup
```

Never share state between tests. Test ordering must not matter.

## Waiting for Conditions

Never use arbitrary `sleep()`. Wait for observable conditions:

```python
# ❌ Fragile
page.click("#submit")
time.sleep(2)
assert page.locator(".success").is_visible()

# ✅ Correct
page.click("#submit")
expect(page.locator(".success")).to_be_visible(timeout=5000)
```

Use `expect(...).to_be_visible()`, `to_have_text()`, `to_have_url()` etc. They poll automatically.

## Flaky Test Prevention

| Cause | Fix |
|-------|-----|
| Timing / race conditions | Use `expect()` with explicit wait conditions |
| Shared test data | Isolate with per-test data creation |
| External service outages | Use wiremock or service virtualization at infra level |
| Animation delays | Disable animations in test environment |
| Port conflicts | Use random ports + health checks |

## Playwright Configuration (Python)

```python
# playwright.config.py / conftest.py
@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 720},
        "ignore_https_errors": True,
    }

@pytest.fixture(scope="session")
def base_url():
    return os.environ.get("E2E_BASE_URL", "http://localhost:8080")
```

Run headless in CI, headed locally for debugging:
```bash
PWDEBUG=1 pytest tests/e2e/ -k test_checkout  # headed with inspector
pytest tests/e2e/ --headed                     # headed without inspector
```

## CI/CD Integration

```yaml
- name: Run E2E tests
  run: pytest tests/e2e/ --tb=short -x
  env:
    E2E_BASE_URL: http://localhost:8080

- name: Upload artifacts on failure
  if: failure()
  uses: actions/upload-artifact@v4
  with:
    name: playwright-artifacts
    path: |
      test-results/
      playwright-report/
```

## Anti-Patterns

- **E2E tests for every scenario** — use the pyramid; only critical journeys belong here
- **Mocking in E2E** — if you're mocking, it's not E2E; move to integration
- **Hardcoded test data** — isolate per test to prevent interference
- **CSS/XPath selectors** — brittle; use role/label/testid
- **Sleeping** — use condition-based waiting
- **Long setup chains** — if setup is complex, it probably belongs in integration tests

## Related

For Playwright-specific implementation (auth state reuse, CI/CD pipeline, artifact management, flaky detection tools): see `e2e-testing` skill.
