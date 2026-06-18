---
id: CAND-14
title: Paginate and sort a large list endpoint
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: page through large result sets; sort by common fields; stable results while paging; consistent performance regardless of how deep the page is
notes: Offset vs cursor pagination (and deep-page performance) is the decision a good SA must make.
---
As a user of a data-heavy screen, I want to page through and sort a long list, so I can find what I
need without loading everything at once.

The list endpoint should return results a page at a time and let me sort by the common columns.
Paging through the list should be stable — I shouldn't see duplicates or skips as I move between
pages — and it should stay responsive even far into a large result set.

Out of scope: client-side virtual scrolling — this is about the server endpoint's contract.
