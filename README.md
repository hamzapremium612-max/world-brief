# 🗞️ The Morning Brief

A daily world-and-Pakistan-affairs brief, built from live RSS feeds. Every
factual claim links to the article it came from. Every historical parallel is
marked as interpretation and carries no source, because it doesn't have one.

Runs on **two rented machines a day**, neither of which is a laptop. All times
Karachi (PKT):

```
8:00am  A CLAUDE CLOUD ROUTINE   cannot reach the open internet
        pushes .fetch-trigger ───┐  it starts the fetch ITSELF
                                 │
8:00am  GITHUB ACTIONS      ◀────┘  can reach the open internet
        python fetch.py             BBC, Guardian, Dawn, Tribune
        commit items.json           answered in ~30 seconds

8:01am  THE ROUTINE, still waiting
        reads items.json            one minute old
        groups, writes, judges precedent
        python render.py            validates and renders
        emails it
        commits briefs/<date>-brief.html   AFTER the send, never before
```

**Why two machines.** Anthropic's sandbox blocks outbound connections to
arbitrary hosts — a first attempt returned zero items from all four feeds with
a `403` on every `CONNECT`. GitHub's runners have open network access but no
judgment. So the fetching happens where the network is, the thinking happens
where the model is, and **the repo is the desk they share**.

`items.json` is therefore **committed on purpose**. It is not a working file;
it is the handoff.

## Why the routine starts the fetch instead of GitHub's schedule

**Because GitHub's scheduler broke, and a schedule cannot be tuned against a
number that will not hold still.**

```
21–26 Aug    cron ~1.5 hours late     absorbed. Briefs arrived.
27 Aug       9h29 and 9h53 late       missed
28 Aug      11h04 and 11h28 late      missed
29–30 Aug    3 to 5 hours late        missed
```

**Four deliveries lost in four days.** Each morning the routine woke at 8:00,
looked once at a file GitHub had not written yet, correctly refused to send
yesterday's news as today's, and emailed a failure notice.

**The first fix failed, and failed usefully.** Two extra crons were scheduled
the *previous evening* so an 11-hour delay would land them before the read.
The delay then moved to 3–5 hours and landed in a gap between the sample
points that had been checked — 0, 1.5, 9.5, 11.5 and 16 hours were verified;
the range between them was not. That failure is what proved the delay is a
**variable, not a constant**, which kills every "just schedule it earlier"
idea at once.

**What is actually broken is narrower than it looked.** Measured on this repo,
minutes apart, on 30 Aug:

```
push-triggered run     16 SECONDS
cron-triggered run     3 to 11 HOURS
```

GitHub deprioritises `schedule` specifically. Everything else fires at once.

So the routine — which has fired at 8:00am every single day without
exception — pushes `.fetch-trigger`, and the workflow listens for that path.
First morning live, 31 Aug: trigger at 8:03:51, `items.json` at 8:04, brief
delivered and archived by 8:10. **Seven minutes, unattended.**

> **The deeper change is not a better clock. It is a WAIT instead of a GUESS.**
> A fetch landing at 8:05 used to produce nothing, because the routine looked
> once at 8:03 and left. Now it stands there watching, so being a few minutes
> late costs nothing.

**The path filter is not optional.** An unfiltered `on: push` fires on the
fetch job's own `items.json` commit and on the nightly brief archive — an
endless loop. Only `.fetch-trigger` starts a fetch.

**The crons remain as a backup**, and if GitHub ever recovers they simply mean
the data is already fresh when the routine wakes. If `STEP 0` fails, nothing
new breaks: `render.py` refuses, the failure notice goes out, and that is
exactly the behaviour that existed before this step.

## The split, and why it exists

```
fetch.py     CODE    gather feeds, check freshness, filter
   ↓  items.json     (committed - the handoff)
THE AGENT     AI     group into themes, write summaries, judge precedent
   ↓  themes.json
render.py    CODE    refuse stale data, validate the response, render
   ↓  brief.html
THE AGENT     AI     email it
```

An earlier version did all of this in Python, calling an AI for the middle
part. It could equally be one long prompt. It is neither, on purpose:

| | Belongs to |
|---|---|
| *Is this story less than 24 hours old?* | **code** — it is subtraction, and subtraction is right every time |
| *Has this feed stopped updating?* | **code** — comparing two numbers |
| *Did the grouping lose any stories?* | **code** — only a loop can prove a negative |
| *Which of these belong together?* | **the agent** — impossible without reading them all |
| *Is there a real historical parallel here?* | **the agent** — and it must be allowed to say no |

> **Code enforces. A prompt requests.**
>
> Ask a model to "only use items from the last 24 hours" and it will be right
> most days, and silent when it isn't. `if age > 24: continue` is right on every
> item, forever.

**And do not assume a feed is sorted.** The stale-feed check originally read
`entries[0]`, which reported *"newest story is 39h old"* for the Guardian while
that feed was serving items 5 hours old. An alarm that fires on a healthy feed
is worse than no alarm — it teaches you to ignore it. It now takes the minimum
age across every entry.

## What `render.py` refuses to trust

The agent's `themes.json` is treated as untrusted input:

- an item index that is out of range is **dropped**
- an index used twice is **counted once**
- **any item the agent forgot lands in "Unsorted"** — and the page says so

Tested against a deliberately broken response: one invalid index, one
duplicate, 43 stories omitted. All 43 were recovered and the omission was
printed on the page.

## The staleness guard at the handoff

Two machines handing a file between them is a new way for the newsletter bug
to come back. If the fetch job fails, the second machine finds **yesterday's
`items.json` sitting there looking perfectly valid** — and a brief dated today
containing yesterday's news is not a partial success, it is a lie.

This guard is why four days of a broken GitHub scheduler cost four briefs
rather than four days of silently stale ones. **It fired correctly every
single time.** The bug was never here.

So `render.py` checks the file's own `built_at` and **refuses**, rather than
warning:

```
REFUSING TO RENDER: items.json is 30.0 hours old (limit 6).
The fetch job did not run today, or ran late. Do NOT send a brief.
```

Exit code 2. No brief is better than a wrong one.

## The watchman, and why he lives in a different building

Two guards above, and neither one can tell you it failed. `render.py` refusing
is the *correct* outcome on a bad morning — and its reward is that no email
arrives. **A healthy morning also produces no alarm.** Success and total
failure look identical from the outside.

> **An alarm that fires when something breaks cannot tell you about something
> that never started.**
>
> Failure has an error message. **Absence has nothing** — no run, no log, no
> exit code. GitHub emails you about a workflow that *fails*; it says nothing
> about one that never *ran*.

So `watchdog.py` does not watch for errors. It watches for absence, and
**fails on purpose** when it finds it, because a failing workflow is the one
thing GitHub already knows how to shout about.

It checks both halves, and it can only do the second because the routine
**commits its brief after the email sends**:

| Evidence | Proves |
|---|---|
| `items.json` fresh, with items | **GitHub** did its half |
| `briefs/<date>-brief.html` exists | **Anthropic's routine** did its half |

Two companies, two schedulers, **neither outage able to hide behind the
other**. And note what that file means: committed *after delivery*, not after
rendering, so its presence says *this brief reached the reader* — not *this
brief was generated*. Only one of those is worth an alarm.

**Four rules it follows, each bought with a mistake:**

- **A separate workflow.** A check inside the fetch job cannot run on the
  morning the fetch job does not run.
- **It runs after everything** (04:00 UTC). Checking early means guessing
  whether a late fetch or a slow routine is still coming — and a guess means
  false alarms.
- **It counts fetches, not minutes.** `built_at` is the *last* commit of the
  morning, so a second successful fetch makes the clock look worse while making
  the system safer. An earlier version warned *"22 minutes to spare"* on a
  morning with two successful fetches that was never in danger.
- **Standard library only.** A monitor with dependencies can fail on its own,
  and a false alarm from the watchman's own plumbing teaches you to ignore him.

**`None` is not `[]`.** When git can't be read, the redundancy check returns
`None`, not an empty list — `[]` is a fact about the system, `None` is a fact
about the observer. A monitor that cannot tell *"the thing is broken"* from
*"I am broken"* is worse than no monitor, so `None` produces a warning about
its own eyesight, never an error about the brief.

**The alarm has been rung.** On 24 Aug a throwaway branch forced exit 1 and the
email arrived. Building a smoke detector and never pressing test is how you end
up with a decoration.

**Still blind to one thing:** the watchdog is itself a scheduled workflow in
this repo. If Actions is down — or auto-disables after 60 days of repository
inactivity — the watchman goes down with it. That is why the routine emails
*"No brief today"* on refusal: it runs on Anthropic's machines and is the only
thing left when GitHub is the thing that failed.

## The freshness guard

Two separate questions that look like one:

```python
MAX_ITEM_AGE_HOURS = 24    # is this STORY news?
STALE_FEED_HOURS   = 24    # is this FEED still alive?
```

24 hours is matched to a daily brief, so each story appears exactly once
rather than yesterday's headlines turning up again this morning.

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

The GitHub Actions job can also be run by hand from the repo's **Actions**
tab (`workflow_dispatch`), which is the fastest way to see whether the
fetching half still works.

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
