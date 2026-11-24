# 0034. AI through OpenRouter: suggestions for parents, a picked-for-you row for the boys

- **Status:** Accepted
- **Date:** 2026-11-23

## Context

ADR 0014 made AI optional and advisory and left the provider open. The owner wants one OpenRouter key to power two
things: recommendations for the parents (what to add) and recommendations for the boys (what to watch next).
ADR 0013 said recommendations are rules a parent can read, not a learned model. Recommending to the boys with AI
needs a careful line so nothing unapproved ever reaches them.

## Decision

- **Provider.** AI goes through OpenRouter's chat completions API. More › AI has: on/off, the key, the model (picked
  from OpenRouter's model list, a small cheap model by default), and a monthly spending cap in dollars. The key is
  stored on the server only, never sent to the page after it is saved (shown as "saved") or to a TV.
- **For parents (advice, ADR 0014 unchanged):**
  - *Suggestions*: a weekly job (ADR 0032) sends the model what each boy has finished and liked lately, and the
    channels already in the library, and asks for YouTube channels and search terms to consider. The server then
    looks those up with yt-dlp, so every suggestion is a real channel or video. They land in the Inbox under
    "Suggested", where a parent adds or dismisses them.
  - *Tags and warnings* on new downloads, as ADR 0014 described, using the same key.
- **For the boys (amends ADR 0013):**
  - The AI may only **order** videos that already passed the visibility pipeline (ADR 0022). It never adds, approves
    or unhides anything. Its output is a list of ids, and any id not in the input list is thrown away.
  - It fills one home row per profile, "Picked for you", rebuilt a few times a day and cached. The other rows stay
    rule-based. A parent can switch the row off per profile.
  - Time-fit and every other rule still apply at the moment the row is drawn, so a picked video that no longer fits
    drops out.
- **Privacy (ADR 0021).** The model gets video titles, channel names, tags and counts. It never gets the boys' names,
  ages or birthdays: profiles are sent as "Child A" and "Child B" with an age band at most. Nothing else about the
  household is sent.
- **Cost.** Every call records its token use and price from OpenRouter's response. When the monthly cap is reached,
  AI jobs stop until the next month and the Jobs page says so. The rule-based rows keep working.
- **Failure.** If OpenRouter is down or the key is wrong, the "Picked for you" row falls back to the rule-based
  "Up next" order and the Jobs page shows the error.

## Consequences

- One key, two uses, and the boys still only ever see approved videos.
- Titles and channel names of what the boys watch leave the house, to OpenRouter and the chosen model's provider.
  This is the cost of the feature; it is off until a key is saved.
- Model output varies; ordering is the only thing it can influence, which keeps the damage of a bad answer small.

## Alternatives

A local model on the home server: private, but weaker, and the iGPU is already busy. Letting AI search YouTube for the boys
directly: breaks ADR 0009. No AI for the boys: rule-based rows only, which the owner asked to go beyond.

## Where it lives

`server/app/ai/` (`openrouter.py`, `suggest.py`, `picks.py`, `budget.py`), `server/migrations/0003_*.sql`
(`ai_calls`, `suggestions`, `picks`), `server/app/api/tv.py` (the row), `server/app/static/admin/app.js` (More › AI,
Inbox › Suggested). Amends ADR 0013 and ADR 0014.
