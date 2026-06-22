---
id: SCEN-109
title: Rate-limit the public API
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: per-client request limits; clear 429 + retry-after when exceeded; limits configurable per plan tier; limiting must not drop accepted requests silently
notes: Fixed-window vs token-bucket and distributed-state are the design choices to surface.
---
**Business value:** A single misbehaving integration can degrade the API for all customers;
per-client limits protect availability and create a lever for plan-based monetisation later.

As an API platform owner, I want to limit how many requests each client can make, so that one
consumer can't degrade the service for everyone.

Each client should have a request limit; when they exceed it they should get a clear, standard
response telling them to back off and when to retry. Limits should differ by the client's plan tier
and be adjustable without a deploy.

**Acceptance criteria:**
- Given a client over its limit, when it calls the API, then it receives a 429 with a retry-after indication.
- Given clients on different plan tiers, then their limits differ according to tier.
- Given a limit change, when applied, then it takes effect without a code deploy.

Out of scope: billing for overage — this ticket is protection, not monetisation.
