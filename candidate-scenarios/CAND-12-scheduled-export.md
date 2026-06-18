---
id: CAND-12
title: Scheduled data export to customer-owned cloud storage
source: draft-candidate
anonymized: true
author: Coco (AI DRAFT — vet/edit/anonymize/re-author before this counts)
expected_key_requirements: daily export on a schedule; delivered to the customer's storage bucket; only their data; failures alerted; credentials handled securely
notes: Credential handling and tenant-data isolation are the security tensions to address.
---
As a data-platform customer, I want a daily export of my data delivered automatically to my own
cloud storage, so my analysts can work with it in our warehouse.

Each day the platform should export the customer's data and deliver it to a storage location they
own. The export must contain only that customer's data. If an export fails, the customer (and we)
should be alerted rather than silently missing a day.

Out of scope: real-time streaming — a scheduled batch is sufficient.
