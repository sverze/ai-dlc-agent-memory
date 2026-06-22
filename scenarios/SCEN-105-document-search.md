---
id: SCEN-105
title: Full-text search across documents with filters
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: keyword search over document contents; filter by type and date; results respect the user's access permissions; results return within a usable time
notes: "Usable time" is vague on purpose; index freshness vs cost is the SA tension.
---
**Business value:** Staff waste time hunting for documents; fast, permission-aware search directly
saves time and prevents accidental exposure of restricted material.

As a knowledge worker, I want to search across all the documents I have access to and narrow the
results, so I can find the right document quickly.

Search should match words in the document contents, not just titles, and let me filter by document
type and date range. I must only ever see results for documents I'm permitted to access. Results
should come back fast enough to feel interactive.

**Acceptance criteria:**
- Given a keyword that appears in a document body, when I search, then that document appears in results.
- Given a document I lack permission for, when I search a term it contains, then it never appears in my results.
- Given a type and date-range filter, when applied, then only matching documents are returned.

Out of scope: semantic / natural-language search — keyword matching is sufficient for this ticket.
