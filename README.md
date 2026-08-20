# 🗞️ The Morning Brief

A daily world-and-Pakistan-affairs brief, built from live RSS feeds. Every
factual claim links to the article it came from. Every historical parallel is
marked as interpretation and carries no source, because it doesn't have one.

Designed to be run by a scheduled cloud agent: **the code does what must be
certain, the agent does what requires judgment.**

## The split, and why it exists

```
fetch.py     CODE    gather feeds, check freshness, filter
   ↓  items.json
THE AGENT     AI     group into themes, write summaries, judge precedent
   ↓  themes.json
render.py    CODE    validate the response, render the page
   ↓  brief.html
THE AGENT     AI     email it
```

An earlier version did all of this in Python, calling an AI for the middle
part. It could equally be one long prompt. It is neither, on purpose:

| | Belongs to |
|---|---|
| *Is this story less than 36 hours old?* | **code** — it is subtraction, and subtraction is right every time |
| *Has this feed stopped updating?* | **code** — comparing two numbers |
| *Did the grouping lose any stories?* | **code** — only a loop can prove a negative |
| *Which of these belong together?* | **the agent** — impossible without reading them all |
| *Is there a real historical parallel here?* | **the agent** — and it must be allowed to say no |

> **Code enforces. A prompt requests.**
>
> Ask a model to "only use items from the last 36 hours" and it will be right
> most days, and silent when it isn't. `if age > 36: continue` is right on every
> item, forever.

## What `render.py` refuses to trust

The agent's `themes.json` is treated as untrusted input:

- an item index that is out of range is **dropped**
- an index used twice is **counted once**
- **any item the agent forgot lands in "Unsorted"** — and the page says so

Tested against a deliberately broken response: one invalid index, one
duplicate, 43 stories omitted. All 43 were recovered and the omission was
printed on the page.

## The freshness guard

Two separate questions that look like one:

```python
MAX_ITEM_AGE_HOURS = 36    # is this STORY news?
STALE_FEED_HOURS   = 24    # is this FEED still alive?
```

Without the second, a publisher can break their feed and the brief keeps
appearing — smaller, quieter, and looking completely normal. During
development, Tribune's newest story was 23 hours old. **One hour from tripping
the warning.** That is how close "working" and "silently degraded" sit.

Anything with no timestamp is dropped too. A feed that can't be dated isn't
fresh — it's *unjudgeable*, which is worse, because you can't tell.

## Reading the page

The design encodes reliability, not decoration:

| | Means |
|---|---|
| 🟢 **Green**, sans-serif | reported. Traceable to a link you can open. |
| 🟤 **Clay**, serif | interpretation. The agent's own knowledge. **No source.** |

Both colour *and* typeface carry it, so the distinction survives greyscale, a
printer, or a reader who never consciously noticed the rule.

**Some days a theme has no Precedent card at all.** That is the point — the
agent is told that a forced comparison is worse than none, because a false
parallel gets repeated in conversation. The refusals are what make the rest
worth believing.

## Running it by hand

```bash
pip install -r requirements.txt

python fetch.py                                    # → items.json
# ... an AI groups and writes, producing themes.json
python render.py items.json themes.json brief.html
```

## Feeds

Four, and **every one was tested before it was written down**:

| Feed | |
|---|---|
| BBC World | ✅ |
| Guardian World | ✅ |
| Dawn | ✅ Pakistan |
| Tribune | ✅ Pakistan |

Al Jazeera and Reuters were **removed**. Both respond normally and return zero
entries. A feed URL remembered rather than checked is how a brief quietly
covers less of the world every day.

## Known limits

- Headlines and feed summaries only — it never fetches article bodies.
- One page of results per feed, capped at 12 items each.
- No memory between issues. It cannot tell you what changed since yesterday.
- The Precedent cards are unverified by design. They are a starting point for
  reading, not a citation.
