---
name: e2e-testing
description: Playwright implementation reference for E2E tests: Page Object Model, auth state reuse, artifact management (screenshots/traces/video), CI/CD integration, and flaky test handling. Use when implementing Playwright tests in Python/pytest. For E2E test design strategy and scope decisions, see designing-tests skill.
origin: ECC
---

# E2E Testing Patterns (Python)

Comprehensive Playwright + pytest patterns for building stable, fast, and maintainable E2E test suites.

## Test File Organization

```
tests/
├── e2e/
│   ├── auth/
│   │   ├── test_login.py
│   │   ├── test_logout.py
│   │   └── test_register.py
│   ├── features/
│   │   ├── test_browse.py
│   │   ├── test_search.py
│   │   └── test_create.py
│   └── api/
│       └── test_endpoints.py
├── pages/
│   └── items_page.py
├── conftest.py
└── pyproject.toml
```

## Page Object Model (POM)

```python
from playwright.sync_api import Page, Locator

class ItemsPage:
    def __init__(self, page: Page) -> None:
        self.page = page
        self.search_input: Locator = page.locator('[data-testid="search-input"]')
        self.item_cards: Locator = page.locator('[data-testid="item-card"]')
        self.create_button: Locator = page.locator('[data-testid="create-btn"]')

    def goto(self) -> None:
        self.page.goto('/items')
        self.page.wait_for_load_state('load')

    def search(self, query: str) -> None:
        with self.page.expect_response(lambda r: '/api/search' in r.url):
            self.search_input.fill(query)

    def get_item_count(self) -> int:
        return self.item_cards.count()
```

## Test Structure

pytest-playwright 默认提供同步 fixtures，无需 `async/await`。

```python
import re
import pytest
from playwright.sync_api import Page, expect
from pages.items_page import ItemsPage

@pytest.fixture
def items_page(page: Page) -> ItemsPage:
    p = ItemsPage(page)
    p.goto()
    return p

class TestItemSearch:
    def test_search_by_keyword(self, items_page: ItemsPage) -> None:
        items_page.search('test')

        assert items_page.get_item_count() > 0
        expect(items_page.item_cards.first()).to_contain_text(re.compile('test', re.I))

    def test_handle_no_results(self, page: Page, items_page: ItemsPage) -> None:
        items_page.search('xyznonexistent123')

        expect(page.locator('[data-testid="no-results"]')).to_be_visible()
        assert items_page.get_item_count() == 0
```

## Configuration

### conftest.py

```python
import pytest
from playwright.sync_api import Browser, BrowserContext, Page

# 全局 browser 选项
def pytest_configure(config):
    config.addinivalue_line('markers', 'slow: mark test as slow')

@pytest.fixture(scope='session')
def browser_context_args(browser_context_args):
    return {
        **browser_context_args,
        'base_url': 'http://localhost:3000',
        'record_video_dir': 'artifacts/videos/',
    }

# Auth 状态复用（避免每个测试都登录）
@pytest.fixture(scope='session')
def auth_context(browser: Browser, tmp_path_factory):
    storage = tmp_path_factory.getbasetemp() / 'auth.json'
    context = browser.new_context()
    page = context.new_page()
    page.goto('/login')
    page.locator('[data-testid="email"]').fill('user@example.com')
    page.locator('[data-testid="password"]').fill('password')
    page.locator('[data-testid="submit"]').click()
    page.wait_for_url('/dashboard')
    context.storage_state(path=str(storage))
    context.close()
    return str(storage)

@pytest.fixture
def auth_page(browser: Browser, auth_context: str) -> Page:
    context = browser.new_context(storage_state=auth_context)
    page = context.new_page()
    yield page
    context.close()
```

### pyproject.toml

```toml
[tool.pytest.ini_options]
testpaths = ["tests/e2e"]
addopts = "--html=playwright-report/index.html --junitxml=playwright-results.xml"

[tool.playwright]
base_url = "http://localhost:3000"
browser = "chromium"
headed = false
```

### 多浏览器 / CI 配置

```bash
# 本地运行（单浏览器）
pytest tests/e2e/

# CI 多浏览器
pytest tests/e2e/ --browser chromium --browser firefox --browser webkit

# CI 并行（需安装 pytest-xdist）
pytest tests/e2e/ -n auto
```

## Flaky Test Patterns

### 隔离

```python
import pytest

@pytest.mark.xfail(reason='Flaky - Issue #123', strict=False)
def test_complex_search(page):
    ...

@pytest.mark.skip(reason='Flaky in CI - Issue #123')
def test_unstable_feature(page):
    ...

# 条件跳过
@pytest.mark.skipif(
    os.getenv('CI') == 'true',
    reason='Flaky in CI - Issue #123'
)
def test_ci_flaky(page):
    ...
```

### 识别 Flakiness

```bash
# 重复运行检测
pytest tests/e2e/test_search.py --count=10  # 需要 pytest-repeat

# 启用重试
pytest tests/e2e/ --reruns=3 --reruns-delay=1  # 需要 pytest-rerunfailures
```

### 常见原因与修复

**Race conditions:**
```python
# Bad: 直接操作，依赖时序
page.click('[data-testid="button"]')

# Good: 使用 Locator，自动等待可见/可交互
page.locator('[data-testid="button"]').click()
```

**Network timing:**
```python
# Bad: 固定等待
page.wait_for_timeout(5000)

# Good: 等待具体条件
with page.expect_response(lambda r: '/api/data' in r.url):
    page.locator('[data-testid="submit"]').click()
```

**Animation timing:**
```python
# Bad: 动画未结束就点击
page.locator('[data-testid="menu-item"]').click()

# Good: 确认元素稳定后点击
menu_item = page.locator('[data-testid="menu-item"]')
menu_item.wait_for(state='visible')
menu_item.click()
```

## Artifact Management

### Screenshots

```python
page.screenshot(path='artifacts/after-login.png')
page.screenshot(path='artifacts/full-page.png', full_page=True)
page.locator('[data-testid="chart"]').screenshot(path='artifacts/chart.png')
```

### Traces

```python
context.tracing.start(screenshots=True, snapshots=True)
# ... test actions ...
context.tracing.stop(path='artifacts/trace.zip')

# 查看 trace
# npx playwright show-trace artifacts/trace.zip
```

### Video

在 `conftest.py` 的 `browser_context_args` 中配置（见上方配置节）。

## CI/CD Integration

```yaml
# .github/workflows/e2e.yml
name: E2E Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: pip install pytest pytest-playwright pytest-html pytest-rerunfailures
      - run: playwright install --with-deps chromium
      - run: pytest tests/e2e/ --reruns=2
        env:
          BASE_URL: ${{ vars.STAGING_URL }}
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report
          path: playwright-report/
          retention-days: 30
```

## Test Report Template

```markdown
# E2E Test Report

**Date:** YYYY-MM-DD HH:MM
**Duration:** Xm Ys
**Status:** PASSING / FAILING

## Summary
- Total: X | Passed: Y (Z%) | Failed: A | Flaky: B | Skipped: C

## Failed Tests

### test_name
**File:** `tests/e2e/features/test_search.py:45`
**Error:** Expected element to be visible
**Screenshot:** artifacts/failed.png
**Recommended Fix:** [description]

## Artifacts
- HTML Report: playwright-report/index.html
- Screenshots: artifacts/*.png
- Videos: artifacts/videos/*.webm
- Traces: artifacts/*.zip
```

## Wallet / Web3 Testing

```python
def test_wallet_connection(page, context):
    context.add_init_script("""
        window.ethereum = {
            isMetaMask: true,
            request: async ({ method }) => {
                if (method === 'eth_requestAccounts')
                    return ['0x1234567890123456789012345678901234567890']
                if (method === 'eth_chainId') return '0x1'
            },
            on: () => {},
            removeListener: () => {},
        }
    """)

    page.goto('/')
    page.locator('[data-testid="connect-wallet"]').click()
    expect(page.locator('[data-testid="wallet-address"]')).to_contain_text('0x1234')
```

## Financial / Critical Flow Testing

```python
import os
import pytest

@pytest.mark.skipif(
    os.getenv('NODE_ENV') == 'production',
    reason='Skip on production - real money'
)
def test_trade_execution(page: Page) -> None:
    page.goto('/markets/test-market')
    page.locator('[data-testid="position-yes"]').click()
    page.locator('[data-testid="trade-amount"]').fill('1.0')

    preview = page.locator('[data-testid="trade-preview"]')
    expect(preview).to_contain_text('1.0')

    with page.expect_response(
        lambda r: '/api/trade' in r.url and r.status == 200,
        timeout=30000
    ):
        page.locator('[data-testid="confirm-trade"]').click()

    expect(page.locator('[data-testid="trade-success"]')).to_be_visible()
```
