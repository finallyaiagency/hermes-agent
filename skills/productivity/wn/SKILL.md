---
name: wn
description: Use when the user wants a "what's next" briefing for today. Produce a concise agenda review covering calendar, to-dos, waiting-for items, and forgotten follow-ups.
version: 1.0.0
author: Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [productivity, briefing, calendar, todo, follow-up, agenda]
    related_skills: [google-workspace]
---

# What's Next Briefing

Generate a short, action-oriented briefing that answers: "What should I pay attention to next?"

## Overview

This skill is the restored `/wn` command. Use it to turn the user's current context into a practical briefing that highlights:

- what is on the agenda today
- what is already on the calendar
- what still needs attention on the to-do list
- what the user is waiting for
- anything the user may have forgotten about or should follow up on

Keep the result concise, useful, and easy to skim. Favor deadlines, blockers, meetings, and next actions over general commentary.

## When to Use

- The user types `/wn`
- The user asks for a "what's next" or "what's on deck" briefing
- The user wants a quick summary of today's commitments and loose ends
- The user wants reminders of waiting-for items or overdue follow-ups

## Briefing Rules

1. **Lead with the most important item first.** If something is urgent today, surface it immediately.
2. **Separate facts from inference.** If you are guessing that something is a follow-up, label it as such.
3. **Do not invent tasks or events.** Only report what you can actually see in the available context or tools.
4. **If a source is unavailable, say so briefly.** For example: "Calendar unavailable in this session."
5. **Prefer bullets over paragraphs.** The output should be fast to scan.
6. **Default to today.** Unless the user specifies otherwise, briefings should focus on the current day and near-term follow-ups.

## Suggested Output Shape

Use this structure unless the user asks for something else:

```text
What's next

Today
- ...

Calendar
- ...

To-dos
- ...

Waiting for
- ...

Forgotten / follow-ups
- ...
```

If a section has nothing useful, keep it short:

```text
Waiting for
- Nothing obvious right now.
```

## Practical Guidance

- Pull from the user's available calendar and task sources if the session has them.
- If the current conversation contains commitments, deadlines, or promises, include them.
- If there are multiple items, rank by urgency and importance.
- If the user is already overloaded, keep the briefing extra short and highlight only the top 3-5 items.

## Common Pitfalls

1. **Dumping everything.** The goal is a briefing, not a full archive.
2. **Hiding blockers.** If something is waiting on another person, call that out clearly.
3. **Treating vague memory as fact.** If you are not sure, mark it as uncertain or omit it.
4. **Ignoring calendar items because they're "obvious."** Calendar is usually the backbone of the briefing.

## Verification Checklist

- [ ] The response starts with a clear "What's next" style header
- [ ] The briefing covers today, calendar, to-dos, waiting-for, and follow-ups when available
- [ ] Nothing is invented or overexplained
- [ ] The final answer is concise and action-oriented
