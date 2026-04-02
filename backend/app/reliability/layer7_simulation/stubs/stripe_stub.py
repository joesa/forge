"""
Stripe API stubs for Wiremock simulation.

Covers:
  - POST /v1/payment_intents  → create payment intent
  - POST /v1/customers        → create customer
  - POST /v1/subscriptions    → create subscription
  - POST /v1/webhooks         → validate webhook signature
"""

from __future__ import annotations

from app.reliability.layer7_simulation.stub_registry import StubConfig, StubMapping


def _stripe_stubs() -> list[StubMapping]:
    """Return all Stripe-related Wiremock stub mappings."""
    return [
        # ── POST /v1/payment_intents ─────────────────────────────────
        StubMapping(
            name="stripe_create_payment_intent",
            request={
                "method": "POST",
                "urlPathPattern": "/v1/payment_intents",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "id": "pi_3Rk7mPLt9xQvZn2w",
                    "object": "payment_intent",
                    "amount": 2000,
                    "currency": "usd",
                    "status": "requires_payment_method",
                    "client_secret": "pi_3Rk7mPLt9xQvZn2w_secret_Hs4K9mNvXy",
                    "created": 1234567890,
                    "livemode": False,
                },
            },
            priority=1,
        ),
        # ── POST /v1/customers ───────────────────────────────────────
        StubMapping(
            name="stripe_create_customer",
            request={
                "method": "POST",
                "urlPathPattern": "/v1/customers",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "id": "cus_Qb8kW9nSpY3oLr",
                    "object": "customer",
                    "email": "test@example.com",
                    "name": "Test Customer",
                    "created": 1234567890,
                    "livemode": False,
                },
            },
            priority=1,
        ),
        # ── POST /v1/subscriptions ───────────────────────────────────
        StubMapping(
            name="stripe_create_subscription",
            request={
                "method": "POST",
                "urlPathPattern": "/v1/subscriptions",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "id": "sub_1Tk9hRNv4yAsWp3x",
                    "object": "subscription",
                    "status": "active",
                    "customer": "cus_Qb8kW9nSpY3oLr",
                    "current_period_start": 1234567890,
                    "current_period_end": 1237246290,
                    "items": {
                        "data": [
                            {
                                "id": "si_Rc9lX0oPqZ4pMs",
                                "price": {
                                    "id": "price_1Vm1jUPx6aCuYr5z",
                                    "unit_amount": 2000,
                                    "currency": "usd",
                                },
                            },
                        ],
                    },
                    "livemode": False,
                },
            },
            priority=1,
        ),
        # ── POST /v1/webhooks ────────────────────────────────────────
        StubMapping(
            name="stripe_webhook_validation",
            request={
                "method": "POST",
                "urlPathPattern": "/v1/webhooks",
            },
            response={
                "status": 200,
                "headers": {"Content-Type": "application/json"},
                "jsonBody": {
                    "id": "evt_1Ul0iTOw5zBtXq4y",
                    "object": "event",
                    "type": "payment_intent.succeeded",
                    "data": {
                        "object": {
                            "id": "pi_3Rk7mPLt9xQvZn2w",
                            "status": "succeeded",
                        },
                    },
                    "livemode": False,
                },
            },
            priority=1,
        ),
    ]


stripe_stub = StubConfig(
    service_name="stripe",
    base_url_pattern="/v1",
    description="Stripe payment API stubs (payment intents, customers, subscriptions, webhooks)",
    mappings=_stripe_stubs(),
)
