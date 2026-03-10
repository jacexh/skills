---
name: designing-tests
description: Use when designing test suites, planning test coverage, choosing which layer (unit/integration/E2E) to test at, writing test cases for microservice chains, state machines, or complex business logic. Use when asking how to scope tests, how to avoid over-testing across service boundaries, or how to apply equivalence partitioning, boundary value analysis, or decision tables.
---

# Designing Tests

Two principles guide effective test design: **layering** (each pyramid level has a distinct focus) and **segmentation** (converge test scope to the smallest meaningful boundary).

---

## Before Designing Any Tests — Read the Docs First

**Tests must be derived from requirements, not from implementation code.**

Reading the code first means you test what the system *does*, not what it *should do*. Bugs become encoded as expected behavior.

**STOP. Before writing any test case, locate and read:**

1. **Product / feature spec** — acceptance criteria, business rules, edge cases defined by product
2. **API contract / interface spec** — endpoints, request/response schema, error codes, authentication
3. **State machine diagram** — valid states, transitions, guards, invalid transition behavior
4. **Non-functional requirements** — idempotency constraints, SLA, consistency guarantees

**If no documentation exists: ask before proceeding.** Do not infer requirements from code.

### Mapping Doc Artifacts to Test Cases

| Documentation artifact | Tests to derive |
|------------------------|----------------|
| Acceptance criteria | Integration test scenarios (one per criterion) |
| Business rule with conditions | Unit tests — apply equivalence partitioning to the rule's conditions |
| API contract (schema + status codes) | Contract tests: valid/invalid inputs, each error code, forbidden fields |
| State transition table | One test per valid transition + one per invalid transition per state |
| Idempotency requirement | Idempotency test cases (repeat same call, assert no duplication) |
| Non-functional requirement | Dedicated test or test tag (e.g., `@pytest.mark.slow` for SLA tests) |

### Common Rationalizations — Do Not Accept These

| Excuse | Reality |
|--------|---------|
| "The code is self-explanatory" | Code shows what it *does*. Docs show what it *should do*. They diverge at every bug. |
| "There are no docs" | Then stop and ask. Tests without specs are guesses that encode current behavior as truth. |
| "I'll check the docs after I draft the tests" | Tests written before reading specs miss requirements and anchor to implementation details. |
| "The existing tests are enough reference" | Existing tests may already be wrong. Always go back to the source. |

---

## The Testing Pyramid

| Layer | Focus | Quantity |
|-------|-------|----------|
| **Unit** | Code implementation logic, boundary values, error paths | Many |
| **Integration** | Business scenarios and interface contracts within one service | Some |
| **E2E** | Critical user journeys through the real system | Few |

### Unit Tests

Test one function/method/class in isolation. Mock **all** external dependencies.

Cover:
- Core logic paths (happy path + variations)
- Boundary values (see Techniques below)
- Error conditions and invalid inputs
- Each branch of conditional logic

### Integration Tests

Test component interactions **within a single service** (e.g., handler → service → repository → DB).

Cover:
- Key business use cases end-to-end within the service
- Interface contracts (what the service accepts and returns)
- Side effects (DB writes, cache invalidation, events emitted)

Mock: external services, downstream APIs. Use real: internal DB, cache (prefer testcontainers).

### E2E Tests

Test user journeys through the real system with no mocks.

Cover: happy paths and primary user journeys only. Keep minimal — one test per critical flow.

---

## Segmentation Principles

### Microservice Chain

For a chain A → B → C → D, test each service independently:

- **Stub** the upstream input (don't trigger A to test B — construct B's input directly)
- **Mock** the downstream dependency (when testing B, mock C)
- Assert only B's behavior

```
❌ Test: trigger A → verify D's state
✅ Test: call B with stubbed input → verify B's output and side effects (C mocked)
```

### Message Queue

- **Producer test**: invoke the action on the service under test → assert the message published matches expected schema/content
- **Consumer test**: publish a test message directly to the queue (or call the handler directly) → assert the resulting side effects
- Never trigger from the upstream service to test a consumer

### State Machine

Test each state transition independently. Never traverse from initial state to final state in one test.

```
❌ Test: order Created → Paid → Shipped → Delivered
✅ Test: given order in Paid state → ship() → assert state is Shipped + shipment record created
✅ Test: given order in Created state → ship() → assert InvalidTransitionError
```

Pattern for each transition:
1. **Given**: set entity directly to source state (bypass prior transitions)
2. **When**: apply the triggering event/action
3. **Then**: assert target state + expected side effects
4. **Also test**: invalid transitions from the same source state

---

## Test Case Design Techniques

### Equivalence Partitioning

Divide the input space into classes where all values in a class produce the same behavior. Test **one representative per class** — testing more within the same class adds no value.

Typical classes for any input:
- Valid range / valid format
- Below minimum / above maximum
- Invalid type or format
- Empty / null / zero

### Boundary Value Analysis

Bugs cluster at boundaries. For every valid range `[min, max]`, test:

```
min-1  (just outside lower)
min    (lower boundary)
min+1  (just inside lower)
max-1  (just inside upper)
max    (upper boundary)
max+1  (just outside upper)
```

Always apply alongside equivalence partitioning — boundaries are the edges of equivalence classes.

### Decision Table

For logic controlled by multiple independent conditions, enumerate combinations explicitly to avoid missing cases.

| Condition A | Condition B | Expected Outcome |
|-------------|-------------|-----------------|
| true        | true        | result X        |
| true        | false       | result Y        |
| false       | true        | error Z         |
| false       | false       | error Z         |

When the number of combinations is large, use **pairwise testing** — cover every pair of condition values at least once rather than all N² combinations.

### State Transition (per test)

Each row in the state transition table becomes one test case:

| Current State | Event    | Expected State | Side Effects |
|---------------|----------|----------------|--------------|
| Created       | pay()    | Paid           | payment recorded |
| Paid          | ship()   | Shipped        | shipment created |
| Created       | ship()   | —              | InvalidTransitionError |

---

## Choosing the Right Layer

```
Is it pure logic with no I/O?
  → Unit

Does it verify a business scenario within one service (with real DB/cache)?
  → Integration

Does it represent a user journey across the full system?
  → E2E

Is it a state machine transition?
  → Unit (transition guard logic) + Integration (full scenario in context)
```

---

## Reference Files

Load when implementing:

| File | When to read |
|------|-------------|
| `references/unit-testing.md` | Writing unit tests: mocking strategy, AAA pattern, test doubles |
| `references/integration-testing.md` | Integration tests: testcontainers, message queue, API contract testing |
| `references/e2e-testing.md` | E2E tests: Page Object Model, selectors, flaky test prevention |
| `references/python-pytest.md` | Python/pytest: fixtures, parametrize, marks, mock patterns |
| `references/go-testing.md` | Go: table-driven tests, httptest, testify, testcontainers-go |
