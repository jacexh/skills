# Test Review Protocol

## When Tests Fail — Investigation Protocol

A failing test is not a problem to eliminate. It is a signal to investigate.

**Never modify a test to make it pass without first determining root cause.**

### Decision Tree

```
Test fails
  ↓
Does the test correctly express the requirement/spec it was derived from?
  ↓ Yes                              ↓ No
Implementation is buggy            Test has a defect
Fix the implementation code        Fix the test to match the spec
```

### Step 1 — Validate the Test Against Its Requirement

Before touching any code:

1. Find the requirement or spec this test was derived from
2. Confirm the test correctly expresses what the spec says should happen
3. Confirm the assertion reflects the expected output per spec — not what the current code happens to return

If the test correctly expresses the requirement → **the bug is in the implementation, not the test.**

### Step 2 — Diagnose the Implementation

Use systematic investigation to understand why the implementation produces wrong output. Do not jump to modifying the test as a shortcut.

### When It Is Correct to Modify a Test

Only modify a test if:

- The **requirement has changed** — document what changed and why before touching the test
- The test was **technically wrong** — it does not correctly express the spec (wrong setup, wrong comparison, wrong scope)
- A **test infrastructure defect** unrelated to behavior (bad fixture, wrong mock scope)

**Changing a test to silence a failure hides a bug. It does not fix it.**

### Common Rationalizations — Do Not Accept These

| Excuse | Reality |
|--------|---------|
| "The expectation seems off" | Off compared to what? Check the spec. The spec is the authority. |
| "The implementation works fine, maybe the test is wrong" | If the implementation produces wrong output per spec, that IS a bug. |
| "It's just a minor difference in output format" | Minor differences are bugs too. Confirm against spec before deciding. |
| "Tweaking the assertion is faster" | Faster to hide the bug. Not faster to fix it. The bug still ships. |
| "The other tests all pass so this test must be wrong" | Other tests are independent. A passing suite does not validate a failing test case. |

---

## Test Design Red Lines

These are absolute prohibitions at the design level. Any test that violates one is invalid — fix it before moving on.

### 1. Vacuous Assertions

A test that does not assert the specific output required by the spec proves nothing. It produces a green result that hides missing or broken behavior.

```python
# ❌ spec says discount must reduce total by 10% — this asserts nothing about that
result = apply_discount(order, percent=10)
assert result is not None

# ✅ assert what the spec actually requires
assert result.total == Decimal("90.00")
```

Common forms:
- `assert result is not None` when spec defines exact output
- `assert response.status_code == 200` with no assertion on response body
- Catching an exception without verifying its type or message matches spec
- `# TODO: add real assertion` left in place

**A test with no meaningful assertion is worse than no test — it reports false confidence.**

### 2. Test Order Dependency

Each test must be able to run in isolation. A test that relies on state created by a previous test is not a test — it is a fragile script.

```python
# ❌ test_b silently depends on test_a having inserted the user first
def test_a_create_user():
    create_user(id="u1")

def test_b_get_user():
    result = get_user("u1")   # fails if run alone
    assert result.id == "u1"

# ✅ each test arranges its own state
def test_get_user_returns_matching_record(db):
    insert_user(db, id="u1", name="Alice")
    result = get_user("u1")
    assert result.id == "u1"
```

Signs of order dependency:
- Arrange section is empty but the test reads from DB / cache
- Test passes in full suite, fails when run individually
- `setUp` / `conftest` fixtures that accumulate state across tests rather than reset it

### 3. Happy-Path-Only Coverage

A test suite that only covers success scenarios is incomplete by design. Bugs live in error paths, boundary violations, and invalid inputs — paths that only exist when requirements explicitly define them.

For every feature under test, the design must include:

| What to cover | Example |
|---------------|---------|
| Valid input → expected output | Normal success case |
| Invalid input → expected error | Rejected request, validation failure |
| Boundary values | Min, max, just-outside-range |
| Missing / null required fields | 400 response, domain error |
| Concurrent or duplicate operations | Idempotency, race conditions if specified |

**If your test list contains only success cases, stop and ask: what does the spec say should happen when inputs are wrong?**
