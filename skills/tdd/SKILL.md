---
name: tdd
description: Apply Test-Driven Development (TDD) discipline — write failing tests first, implement minimal code to pass, then refactor. Use when building new features, fixing bugs, or refactoring. Language-agnostic; works with Python, Go, TypeScript, and others.
---

# Test-Driven Development (TDD)

A discipline for writing software by letting tests drive the design. The core loop: **Red → Green → Refactor**.

**Announce at start:** "I'm applying the TDD skill."

---

## The Red-Green-Refactor Cycle

```
RED    → Write a failing test that describes the next behavior
GREEN  → Write the minimal code that makes the test pass (no more)
REFACTOR → Clean up the code without changing behavior; tests stay green
```

**Never skip a step.** Running the test and seeing it fail (RED) before implementing is not optional — it proves the test actually catches the missing behavior.

---

## Rules

1. **No production code without a failing test.** If you're writing code that isn't forced by a failing test, stop.
2. **Write the simplest code that passes.** Hardcode, fake it, do whatever makes the test green. Generalize in future cycles.
3. **One test at a time.** Don't write multiple failing tests before making one green.
4. **Refactor only on green.** Never refactor while red. Never add new behavior while refactoring.
5. **Commit on green.** Each green is a safe point. Commit frequently.
6. **Tests are the spec.** If the test is hard to write, the design is wrong. Simplify the interface first.

---

## The Cycle in Practice

### Step 1 — RED: Write a failing test

Write the test as if the API already exists exactly as you want it. Don't look at existing code. Design the interface from the caller's perspective.

```python
# Python
def test_cart_total_with_single_item():
    cart = Cart()
    cart.add(Item("apple", price=1.50), quantity=2)
    assert cart.total() == 3.00
```

```go
// Go
func TestCartTotalWithSingleItem(t *testing.T) {
    cart := NewCart()
    cart.Add(Item{Name: "apple", Price: 1.50}, 2)
    assert.Equal(t, 3.00, cart.Total())
}
```

```typescript
// TypeScript
test("cart total with single item", () => {
  const cart = new Cart();
  cart.add(new Item("apple", 1.50), 2);
  expect(cart.total()).toBe(3.00);
});
```

**Run the test. Confirm it fails with a meaningful error** (not a syntax error — a missing symbol or assertion failure). If it passes already, the test is wrong or the behavior already exists.

### Step 2 — GREEN: Minimal implementation

Write the least code needed to pass. Literally the least.

```python
class Cart:
    def __init__(self):
        self._items = []

    def add(self, item, quantity):
        self._items.append((item, quantity))

    def total(self):
        return sum(item.price * qty for item, qty in self._items)

class Item:
    def __init__(self, name, price):
        self.name = name
        self.price = price
```

**Run the test. Confirm it passes (GREEN).** If it doesn't, fix the implementation — don't change the test.

### Step 3 — REFACTOR: Clean without changing behavior

With tests green, improve the code. Extract duplication, rename for clarity, restructure.

```python
# Refactored: Item knows its own line total
class Item:
    def __init__(self, name, price):
        self.name = name
        self.price = price

    def line_total(self, quantity: int) -> float:
        return self.price * quantity

class Cart:
    def __init__(self):
        self._lines: list[tuple[Item, int]] = []

    def add(self, item: Item, quantity: int) -> None:
        self._lines.append((item, quantity))

    def total(self) -> float:
        return sum(item.line_total(qty) for item, qty in self._lines)
```

**Run all tests again. Still green.** If anything breaks, you accidentally changed behavior — revert the refactor.

**Commit.**

---

## Bug Fixing with TDD

Always reproduce a bug with a failing test *before* fixing it.

```
1. Write a test that exposes the bug → RED
2. Fix the bug → GREEN
3. Refactor if needed → GREEN
4. Commit
```

This guarantees the bug is fixed and won't regress.

---

## Outside-In vs Inside-Out

**Inside-Out (Chicago/Classic TDD)**
- Start with the smallest unit (pure functions, data structures)
- Build up toward higher-level components
- Good for: well-understood domains, algorithmic code
- Risk: design misfit between layers discovered late

**Outside-In (London/Mockist TDD)**
- Start with an acceptance/integration test (fails)
- Implement layer by layer; mock collaborators not yet built
- Drive inner layers' interfaces from how outer layers need to use them
- Good for: web APIs, event-driven systems, unknown domains
- Risk: over-mocking; tests don't catch integration issues

Both are valid. Choose based on context. Many teams use outside-in at the feature level and inside-out at the unit level.

---

## Test Doubles

Use the simplest double that works. Don't mock what you own.

| Double | When to use |
|--------|------------|
| **Fake** | Real working implementation, simplified (in-memory DB, fake clock) |
| **Stub** | Provide canned responses for queries; don't verify calls |
| **Mock** | Verify that specific interactions occurred; use sparingly |
| **Spy** | Record calls on a real object; assert after the fact |

```python
# Prefer fakes over mocks for infrastructure
class FakeUserRepository:
    def __init__(self):
        self._users: dict[str, User] = {}

    def save(self, user: User) -> None:
        self._users[user.id] = user

    def find_by_id(self, user_id: str) -> User | None:
        return self._users.get(user_id)

def test_register_user_saves_to_repository():
    repo = FakeUserRepository()
    service = UserService(repo)
    service.register(name="Alice", email="alice@example.com")
    assert repo.find_by_id("alice@example.com") is not None
```

---

## When Tests Are Hard to Write

If writing the test is painful, the design is telling you something:

| Symptom | Signal | Fix |
|---------|--------|-----|
| Needs many objects to set up | Too much coupling | Break dependencies |
| Can only test through side effects | Logic buried in I/O | Separate pure logic |
| Must mock many things | Too many collaborators | Reduce responsibilities |
| Test mirrors implementation exactly | Testing internals | Test behavior, not structure |
| Tests break on every refactor | Wrong abstraction level | Test the public contract |

---

## Triangulation

When the simplest implementation would just be `return 42`, write a second test that forces generalization.

```python
def test_add_returns_sum():
    assert add(2, 3) == 5   # Could fake with: return 5

def test_add_with_different_values():
    assert add(10, 1) == 11  # Forces real implementation
```

---

## TDD Rhythms

**Micro-cycle (seconds to minutes)**
Write test → run → implement → run → refactor → run → commit

**Feature cycle (minutes to hours)**
Write acceptance test → drive out units via TDD → acceptance test goes green → commit

**Refactoring cycle (any time on green)**
Rename → extract → inline → move → simplify → verify green → commit

---

## Anti-Patterns to Avoid

- **Test-last**: Writing tests after implementation means tests confirm code, not drive design
- **God test**: One test that covers everything — split into focused tests
- **Fragile test**: Breaks when unrelated code changes — test behavior, not structure
- **Slow test**: Tests that hit the network/disk/sleep — use fakes and in-memory stores
- **Commented-out tests**: Just delete them; if the behavior matters, write a real test
- **Mocking internals**: If you mock private methods you're testing implementation, not behavior
- **Skipping RED**: Writing code then writing a test that passes is not TDD

---

## Checklist for Each Cycle

- [ ] Test describes one specific behavior
- [ ] Test name reads like a sentence (what it does, not how)
- [ ] Test fails before implementation (saw RED)
- [ ] Implementation is the minimum needed
- [ ] Test passes (GREEN confirmed by running, not assumed)
- [ ] Code is clean after refactor
- [ ] All tests still pass after refactor
- [ ] Committed on green
