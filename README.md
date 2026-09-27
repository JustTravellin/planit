# URBOS

This repository hosts URBOS's internal tools. Nothing here is linked from a
public homepage — each tool lives at its own quiet URL and is handed out
person-by-person.

## Celebrations planner (secret feature)

A shared planner for a wedding, engagement party, or similar celebration —
built so a small circle of people (the hosts, the couple, whoever's helping
run the day) can collect and edit every detail in one place, without it
being discoverable by anyone they didn't personally send a link to.

There's no sign-up page, no list of events, and no link to it anywhere in
this app. Access is entirely link-based: whoever creates the plan generates
one invite link per person from inside the app, and that link is the only
way in. Revoke a link at any time and it stops working immediately for that
person, without affecting anyone else's.

### What it tracks

- **Overview** — event name, date, time window, location, hosts, guest(s)
  of honour, expected guest count, theme/vibe, and a free-text notes field
  for anything that doesn't fit elsewhere.
- **Run Sheet** — a timed, phase-by-phase schedule for the day.
- **Zones & Layout** — every gathering space (anchor tent, lounge, bar,
  dining, dance floor, fireside, games, photo spot...), its capacity, and
  its weather fallback.
- **Guests** — RSVP status, plus-ones, dietary/access needs, seating/zone.
- **Vendors & Budget** — every vendor or hire item by category, estimated
  vs. actual cost, deposit status, and booking status, with a running
  budget total at the top of the tab.
- **Shopping List** — decor and supplies to buy, hire, or borrow, who's
  getting each one, and (for borrowed/hired items) a return-by date.
- **Tasks** — the jobs that are easy to forget: permits and siting
  approval, pest/bug control, fire season checks, parking and transport,
  toilets, insurance and neighbour notices, weather contingency — with an
  assignee, due date, and status on each.
- **Contacts** — every vendor and helper's phone/email in one place for
  the day itself.
- **Collaborators** (owner only) — generate or revoke a person's invite
  link, and see who currently has access.

Anyone with a link (owner or collaborator) can view and edit all of the
above except Collaborators, which only an owner-role invite can see.

### Running it locally

```bash
npm run install:all   # installs the server and web app
npm run dev            # runs both together (API on :4700, web app on :5173)
```

### Creating a plan

There's no "new plan" button in the UI — that's intentional. Provision a
plan from a terminal you trust, and it prints your own owner link:

```bash
npm run create-plan -- \
  --title "Sarah & Tom's Engagement Party" \
  --date 2026-11-14 --start 16:00 --end 22:00 \
  --address "Junortoun, VIC" \
  --hosts "Ian & family" \
  --guests-of-honour "Sarah & Tom" \
  --guest-count 70 \
  --theme "Warm lanterns, vintage glass, garden florals" \
  --owner-name "Ian"
```

This prints a link like `http://localhost:5173/p/<token>`. Open it, then use
the **Collaborators** tab to generate a separate link for each person
helping you plan — each one can be revoked independently later.

If you deploy the server and web app somewhere other than localhost, pass
`--base-url https://your-domain` to `create-plan` (and generate
collaborator links from the deployed app itself, which already knows its
own URL).

### How it's built

- `server/` — a small Express API. Data is stored in a single JSON file
  (`server/data/db.json`, gitignored) rather than a database — this is a
  low-traffic tool for a handful of people, not a service that needs to
  scale. Every request (other than `/api/health`) requires a valid,
  non-revoked invite token sent as `Authorization: Bearer <token>`; there
  is no endpoint that lists or discovers plans.
- `web/` — a Vite + React single-page app. The only meaningful route is
  `/p/:inviteToken`; every other path (including `/`) renders nothing.
