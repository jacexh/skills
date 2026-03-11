# Idempotency Testing Reference

Idempotency testing verifies that performing the same operation multiple times produces the same outcome without unintended side effects. Must-test scenarios:

- **PUT / DELETE**: inherently required to be idempotent by HTTP semantics
- **POST with idempotency key**: same key submitted twice must not create duplicates
- **Message consumers**: at-least-once delivery means duplicates will arrive — consumers must handle them safely

## Pattern: Act → Assert → Act Again → Assert Same State

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

## POST + Idempotency Key

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

## PUT Idempotency

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

## Message Consumer Idempotency

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
