# Hermes Desktop To-Do List

Started: 2026-06-15

## Status

| # | Task | Status | Time Spent | Notes |
|---|---|---|---|---|
| 1 | Update the Hermes Desktop app in the safest, best way possible and document the correct update flow | complete | 35m | Desktop app updates via the modal; CLI installs use `hermes update` in PowerShell from the Hermes root; stash from update stays preserved |
| 2 | Change the Flipping Income Chart source to the new Groundbnb Store Google Sheet | complete | 0m | Updated to spreadsheet `12TELzT2bzIxdry3pyLvSv3hdWJpkdvGC25aSlvsBq94`; export now pulls `Inventory Register` + `Sales Ledger` |
| 3 | Investigate why Moneypenny returned `Response remained truncated after 3 continuation attempts` | pending | 0m | Need to inspect failure mode and possible fixes |
| 4 | Fix cron job responses so they do not start with `Cronjob Response` and job IDs | pending | 0m | Keep the message human-readable |
| 5 | Delay the daily passport renewal reminder until July 17, 2026 | pending | 0m | Do not stop/delete permanently |
| 6 | Figure out Moneypenny voice behavior for typed prompts vs voice prompts | pending | 0m | Determine whether typed prompts can still receive audio replies |
| 7 | Fix Radar continuity for the Ground B&B Google Sheet and row/formula context | pending | 0m | Must remember prior work and interpret sheet row/cell references correctly |
| 8 | Investigate Codex fallback when credits expire or run out | pending | 0m | Review yesterday’s history and the credit-warning skill |
| 9 | Test whether Nemotron Free can handle Calendar, Tasks, Docs, and Sheets consistently | pending | 0m | Compare against GPT-5.5 |

## Notes

- 10 | Find out what happened to Moneypenny's income chart dashboard mods with the color-coded KPIs and added margin | pending | 0m | Check whether today's refresh rolled back one or more versions or if the same Vercel URL now points to another page
- Mark items as `complete` when finished.
- Update `Time Spent` with the best current estimate when an item is completed.
- Keep notes short and concrete.
