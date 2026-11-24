# 0014. AI is optional and only advises the parent

- **Status:** Accepted
- **Date:** 2026-11-22

## Context

AI can save the parents time: tagging videos, screening transcripts, suggesting channels, writing a weekly summary.
WhatsOn set the rule that AI is optional and never invents results. Here a wrong AI call could put the wrong video in
front of a child.

## Decision

- The whole system works with AI turned off.
- The model is a setting: a local model or a cloud one, chosen in the admin page, as in WhatsOn.
- AI output is **advice to a parent**, shown as such, and never an action on its own:
  - **Tags** on download: topic, age fit, energy (calm to hyper), learning or fun. AI tags are marked as AI and a
    parent's edit wins. Tags feed rows and categories.
  - **Screening**: reads the transcript and description and adds warnings to the inbox item (language, scary themes,
    unboxing, heavy selling).
  - **Channel report**: a summary of a channel's recent uploads before subscribing.
  - **Suggestions**: channels or videos to consider, from what the boys finish watching. They go to the inbox.
  - **Search for the parent** in plain words over the local library; results are always real library items.
  - **Weekly digest** of what each child watched.
  - **Playlist drafts** and **quiz questions** for a parent to accept.
  - **Calmer titles and thumbnails**: offered as an alternative the parent switches on per item or channel.
- AI never approves, hides, assigns or changes limits.
- **Tags never depend on AI.** A parent can tag any item or container by hand in the admin page from the first
  milestone, and a container's tags are inherited by its items. AI only fills in tags faster.
- While a rule that restricts by tag is active (calm-only evenings, category budgets), an item with no tag of that
  kind is **hidden**, not shown.
- Voice search on the TV is speech-to-text plus the normal local search. It is not an AI feature. It uses the TV's
  own speech recognition, which on Google TV sends the audio to Google; it can be switched off per TV.
- Children's names and watch history are not sent to a cloud model. Titles, descriptions and transcripts of public
  videos may be.

## Consequences

- Parents stay in the loop; AI mistakes cost a wrong warning or a wrong tag, which a parent can fix.
- Transcripts need subtitles or speech-to-text, which costs compute on the server.
- With a cloud model, public video text leaves the house. A local model avoids that at lower quality.

## Alternatives

Auto-approve on a clean AI screen: fast, and unsafe when it is wrong. No AI at all: all tagging and screening by hand.

## Where it lives

`server/app/ai/` (`tags.py`, `screen.py`, `suggest.py`, `digest.py`, `provider.py`).
