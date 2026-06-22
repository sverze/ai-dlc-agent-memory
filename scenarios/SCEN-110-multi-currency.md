---
id: SCEN-110
title: Display prices in the customer's local currency
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: show prices in the user's currency; rates refreshed regularly; the charged amount matches the displayed amount; rounding rules consistent
notes: Rate source, refresh cadence, and display-vs-settlement currency are open — fertile SA ground.
---
**Business value:** Showing foreign customers prices in an unfamiliar currency depresses conversion;
local-currency display improves checkout completion in international markets.

As an international customer, I want to see prices in my own currency, so I understand what I'll
actually pay.

Prices should be shown converted to the customer's local currency using reasonably current exchange
rates. The amount we ultimately charge must match what was shown at the point of purchase, with
consistent rounding.

**Acceptance criteria:**
- Given a customer in a supported region, when they view a price, then it is shown in their local currency.
- Given a displayed price, when the customer is charged, then the charged amount matches what was shown.
- Given rounding, then it is applied consistently and documented.

Out of scope: tax calculation and localized payment methods — display of price only.
