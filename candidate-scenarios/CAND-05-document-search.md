---
id: CAND-05
title: Full-text search across documents with filters
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: keyword search over document contents; filter by type and date; results respect the user's access permissions; results return within a usable time
notes: "Usable time" is vague on purpose; index freshness vs cost is the SA tension.
---
As a knowledge worker, I want to search across all the documents I have access to and narrow the
results, so I can find the right document quickly.

Search should match words in the document contents, not just titles, and let me filter by document
type and date range. I must only ever see results for documents I'm permitted to access. Results
should come back fast enough to feel interactive.

Out of scope: semantic / natural-language search — keyword matching is sufficient for this ticket.
