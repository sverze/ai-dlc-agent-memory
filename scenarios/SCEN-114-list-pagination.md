---
id: SCEN-114
title: Paginate and sort a large list endpoint
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: page through large result sets; sort by common fields; stable results while paging; consistent performance regardless of page depth
notes: Offset vs cursor pagination (and deep-page performance) is the decision a good SA must make.
---
**Business value:** Data-heavy screens time out and frustrate users on large accounts; reliable
pagination keeps the product usable as customers' data grows.

As a user of a data-heavy screen, I want to page through and sort a long list, so I can find what I
need without loading everything at once.

The list endpoint should return results a page at a time and let me sort by the common columns.
Paging through the list should be stable — I shouldn't see duplicates or skips as I move between
pages — and it should stay responsive even far into a large result set.

**Acceptance criteria:**
- Given a large result set, when I request a page, then I get that page without loading the whole set.
- Given I sort by a supported column, then results are ordered accordingly and remain stable while paging.
- Given I page deep into the set, then response time stays comparable to early pages.

Out of scope: client-side virtual scrolling — this is about the server endpoint's contract.
