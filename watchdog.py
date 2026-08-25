"""The dead man's switch for the Morning Brief.

This file fetches nothing, renders nothing and sends nothing. Once a day,
after the fact, it asks three questions:

    1. Did the feeds land in time for the routine to read them?
    2. Was there anything in them?
    3. Did the routine actually DELIVER a brief?

and it fails on purpose when any answer is no - because GitHub emails you
about a workflow that fails and says nothing at all about a workflow that
never ran. Silence was the failure this project actually had.

WHY QUESTION 3 CAN BE ASKED AT ALL. Until 2026-08-25 the routine sent an email
and left nothing behind, so this file could only ever watch the fetching half.
It now commits briefs/<date>-brief.html AFTER the send succeeds. That means a
GitHub machine can check an Anthropic machine's work: two companies, two
schedulers, neither outage able to hide behind the other.

And note what that file's presence proves. It is committed after delivery, not
after rendering, so it means "this brief reached Hamza" - not "this brief was
generated". Those are different claims and only one of them is worth an alarm.

Three design choices worth knowing:

1. SEPARATE WORKFLOW. A check living inside the fetch job cannot run on the
   morning the fetch job does not run. The watchman must not sleep in the
   building he is watching.

2. IT RUNS AFTER EVERYTHING. Checking early would mean guessing whether a late
   fetch or a slow routine is still coming, and a guess means false alarms.

3. IT COUNTS ATTEMPTS, NOT MINUTES. built_at comes from the LAST commit of the
   morning, so a second successful fetch makes the clock look WORSE while
   making the system safer. An earlier draft warned "22 minutes to spare" on a
   morning with two successful fetches that was never in danger.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# Copied from the machines being watched, not chosen here:
#   the Claude routine's cron is 0 3 * * *
#   render.py refuses any items.json older than MAX_DATA_AGE_HOURS = 6
# If either changes, this file is wrong until it changes too.
ROUTINE_HOUR_UTC = 3
RENDER_LIMIT_HOURS = 6

BOT = "morning-brief-bot"
LOOKBACK_HOURS = 12
BRIEF = "briefs/{date}-brief.html"


def fetches_before(start, end):
    """Timestamps of bot commits in a window. None means git could not answer.

    None and [] are deliberately different. [] is a fact about the system.
    None is a fact about THIS SCRIPT - usually a shallow clone with no history
    to read. A monitor that cannot tell "the thing is broken" from "I am
    broken" is worse than no monitor, so the two never share a return value.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--author=" + BOT,
             "--since=" + start.isoformat(), "--until=" + end.isoformat(),
             "--format=%cI"],
            capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


now = datetime.now(timezone.utc)
routine_ran = now.replace(hour=ROUTINE_HOUR_UTC, minute=0, second=0, microsecond=0)

if now < routine_ran:
    print("The routine has not read the file yet today. Nothing to check.")
    sys.exit(0)

with open("items.json", encoding="utf-8") as f:
    data = json.load(f)

built = datetime.fromisoformat(data["built_at"])
items = len(data.get("items", []))
age_hours = (routine_ran - built).total_seconds() / 3600
landed = fetches_before(routine_ran - timedelta(hours=LOOKBACK_HOURS), routine_ran)

# Today's date exactly - no tolerance. On a DAILY system, accepting
# yesterday's file would hide a whole missed morning, which is the entire
# thing this check exists to catch.
wanted = BRIEF.format(date=routine_ran.date().isoformat())
delivered = os.path.exists(wanted)

print("routine ran at   : " + routine_ran.isoformat())
print("items.json built : " + built.isoformat())
print("age it saw       : " + str(round(age_hours, 2)) + " h   (limit "
      + str(RENDER_LIMIT_HOURS) + ")")
print("items available  : " + str(items))
print("fetches in time  : " + ("unknown" if landed is None else str(len(landed))))
print("brief delivered  : " + (wanted if delivered else "NOT FOUND (" + wanted + ")"))

# ---- the alarms, ordered so the FIRST thing that broke is what you hear
# ---- about. A stale fetch also produces no brief; reporting the missing
# ---- brief would name the symptom and hide the cause.

if age_hours < 0:
    # items.json was written AFTER the routine read it, so this file is NOT
    # what the routine saw and its age says nothing about what happened. The
    # scheduled path never produces this - the fetch runs three hours before
    # the read. It shows up when a fetch is triggered by hand later in the
    # day, or when GitHub runs catastrophically late.
    #
    # Passing quietly here would be the bug this whole file exists to prevent:
    # a negative number sails straight through the staleness test below and
    # the guard looks like it ran. It did not. Say so, and let the delivery
    # check be the judge.
    print("::warning::items.json was built AFTER the routine read it ("
          + str(round(-age_hours, 1)) + "h after), so this is not the file the "
          + "routine saw and its age cannot be judged. Usually a fetch run by "
          + "hand. Falling back to the delivery check alone.")

elif age_hours > RENDER_LIMIT_HOURS:
    print("::error::NO BRIEF TODAY. items.json was " + str(round(age_hours, 1))
          + " hours old when the routine read it, past the "
          + str(RENDER_LIMIT_HOURS) + "-hour limit. No fetch landed in time and "
          + "render.py correctly refused to send yesterday's news as today's.")
    sys.exit(1)

if items == 0:
    print("::error::NO BRIEF TODAY. items.json was fresh but held zero items. "
          + "Every feed returned nothing - check whether the feed URLs moved.")
    sys.exit(1)

if not delivered:
    # The half this file was blind to until 2026-08-25. Fresh feeds were
    # sitting there and nothing came out, so the failure is on the Anthropic
    # side: the routine did not fire, or it stopped partway.
    freshness = ("fresh data was available" if age_hours < 0
                 else "items.json was only " + str(round(age_hours, 1)) + "h old")
    print("::error::THE FETCH WORKED BUT NO BRIEF WAS DELIVERED. " + freshness
          + " with " + str(items) + " items, so render.py would have passed. "
          + "Expected " + wanted + ". The Claude routine did not run, failed "
          + "partway, or the email never sent.")
    sys.exit(1)

# ---- notes. Nothing is broken, so these never email. ----

if landed is None:
    print("::warning::Could not read git history, so redundancy is unknown. "
          + "Check that the workflow sets fetch-depth on actions/checkout.")
elif len(landed) == 1:
    print("::warning::The brief went out on ONE successful fetch. The spare "
          + "did not land. One dropped run tomorrow means no brief.")

print("OK - " + str(items) + " fresh items, "
      + ("unknown" if landed is None else str(len(landed))) + " fetch(es) in time, "
      + "brief delivered and archived at " + wanted)
