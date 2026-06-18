---
id: CAND-09
title: Rate-limit the public API
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: per-client request limits; clear 429 + retry-after when exceeded; limits configurable per plan tier; limiting must not drop accepted requests silently
notes: Fixed-window vs token-bucket and distributed-state are the design choices to surface.
---
As an API platform owner, I want to limit how many requests each client can make, so that one
consumer can't degrade the service for everyone.

Each client should have a request limit; when they exceed it they should get a clear, standard
response telling them to back off and when to retry. Limits should differ by the client's plan tier
and be adjustable without a deploy.

Out of scope: billing for overage — this ticket is protection, not monetisation.
