---
id: SCEN-115
title: Capture and honour user consent (and withdrawal)
source: synthetic-dry-run
anonymized: true
author: Coco (AI BA/PM persona — SYNTHETIC dry-run, not a real external reviewer)
expected_key_requirements: record consent with timestamp and version; user can withdraw anytime; processing stops on withdrawal; an auditable history of consent changes
notes: Versioning of consent text and what "stop processing" concretely means are key clarifications.
---
**Business value:** Demonstrable consent management is a regulatory requirement in several markets;
getting it wrong risks fines and blocks expansion into those markets.

As a user, I want to give and withdraw consent for how my data is used, so I stay in control of my
information and the company stays compliant.

When I give consent, the system should record what I agreed to, the version of the terms, and when. I
should be able to withdraw any consent at any time, after which the corresponding processing stops.
There should be a reliable history of my consent decisions for compliance purposes.

**Acceptance criteria:**
- Given I grant consent, then the system records the consent, the terms version, and a timestamp.
- Given I withdraw consent, when processing that relied on it next runs, then it does not proceed.
- Given a compliance query, then a complete history of my consent grants and withdrawals is available.

Out of scope: the legal wording of the consent notices themselves — assume those are provided.
