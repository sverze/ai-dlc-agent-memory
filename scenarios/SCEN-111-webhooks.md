---
id: SCEN-111
title: Deliver event webhooks to customer endpoints
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: POST events to a customer URL; retry with backoff on failure; dead-letter after repeated failures; deliveries verifiable/authentic; at-least-once with visible delivery status
notes: Ordering and exactly-once-vs-at-least-once are the hard guarantees to pin down.
---
**Business value:** Integrators currently poll the API, adding load and latency; push webhooks make
integrations real-time and reduce wasted API traffic.

As an integrator, I want to receive events from the platform at my own endpoint, so my systems can
react in near-real-time without polling.

The platform should send each event to my configured URL and retry with backoff if my endpoint is
temporarily down, giving up to a dead-letter state after repeated failures. I need to be able to
verify a delivery genuinely came from the platform, and to see the delivery status of recent events.

**Acceptance criteria:**
- Given an event occurs, when my endpoint is healthy, then I receive an HTTP POST with the event payload.
- Given my endpoint is temporarily failing, when it recovers, then pending deliveries are retried with backoff, and abandoned to a dead-letter state after repeated failure.
- Given a received delivery, then I can verify it authentically originated from the platform.

Out of scope: a replay UI for old events — current/near-term delivery only.
