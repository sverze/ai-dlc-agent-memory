---
id: SCEN-002
title: Export a filtered report to CSV
source: illustrative
anonymized: true
author: build-team (ILLUSTRATIVE — replace with an external author for the real gate)
expected_key_requirements: export respects active filters; CSV download for up to 100k rows; export runs without blocking the UI
notes: Large-export performance is implied, not stated — a good SA should surface async/streaming as a clarification or added constraint.
---
As an analyst, I want to export the currently filtered report to a CSV file so that I can
share the data with stakeholders who do not have access to the application.

The export must reflect whatever filters I currently have applied, and should handle reports
of up to 100,000 rows. I should be able to keep using the application while the export is prepared.

Acceptance: the downloaded file opens cleanly in Excel and Google Sheets, with a header row
matching the on-screen column names.
