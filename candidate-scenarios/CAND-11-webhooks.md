---
id: CAND-11
title: Deliver event webhooks to customer endpoints
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: POST events to a customer URL; retry with backoff on failure; dead-letter after repeated failures; deliveries verifiable/authentic; at-least-once with visible delivery status
notes: Ordering and exactly-once-vs-at-least-once are the hard guarantees to pin down.
---
As an integrator, I want to receive events from the platform at my own endpoint, so my systems can
react in near-real-time without polling.

The platform should send each event to my configured URL and retry with backoff if my endpoint is
temporarily down, giving up to a dead-letter state after repeated failures. I need to be able to
verify a delivery genuinely came from the platform, and to see the delivery status of recent events.

Out of scope: a replay UI for old events — current/near-term delivery only.
