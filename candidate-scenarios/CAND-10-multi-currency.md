---
id: CAND-10
title: Display prices in the customer's local currency
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: show prices in the user's currency; rates refreshed regularly; the charged amount matches the displayed amount; rounding rules consistent
notes: Rate source, refresh cadence, and display-vs-settlement currency are open — fertile SA ground.
---
As an international customer, I want to see prices in my own currency, so I understand what I'll
actually pay.

Prices should be shown converted to the customer's local currency using reasonably current exchange
rates. The amount we ultimately charge must match what was shown at the point of purchase, with
consistent rounding.

Out of scope: tax calculation and localized payment methods — display of price only.
