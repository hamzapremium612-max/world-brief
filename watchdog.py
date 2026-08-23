"""The dead man's switch for the Morning Brief.

This file fetches nothing, renders nothing and sends nothing. Once a day,
after the fact, it asks:

    Did this morning's brief have fresh data - and did it have a spare?

and it FAILS ON PURPOSE when the answer to the first half is no, because
GitHub emails you about a workflow that fails and says nothing at all about a
workflow that never ran. Silence was the failure this project actually had.

Three design choices worth knowing:

1. SEPARATE WORKFLOW. A check living inside the fetch job cannot run on the
   morning the fetch job does not run. The watchman must not sleep in the
   building he is watching.

2. IT RUNS AFTER THE ROUTINE. Checking at 7:40am would mean guessing whether
   a late fetch is still on its way, and a guess means false alarms.

3. IT COUNTS ATTEMPTS, NOT MINUTES. The first version of this file measured
   how old items.json was and warned when the number looked tight. That was
   wrong. built_at comes from the LAST commit of the morning, so a second
   successful run makes the number look WORSE while making the system safer.
   On 23 Aug it reported "22 minutes to spare" on a morning that had two
   successful fetches and was never in danger. What actually matters is how
   many fetches landed before the routine read the file.
"""
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone

# Copied from the machine being watched, not chosen here: the Claude routine's
# cron is 0 3 * * *, and render.py refuses any items.json older than
# MAX_DATA_AGE_HOURS = 6. If either changes, this file is wrong until it does.
ROUTINE_HOUR_UTC = 3
RENDER_LIMIT_HOURS = 6

BOT = "morning-brief-bot"
LOOKBACK_HOURS = 12          # wide enough to catch every plausible fetch time


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


with open("items.json", encoding="utf-8") as f:
    data = json.load(f)

built = datetime.fromisoformat(data["built_at"])
items = len(data.get("items", []))

now = datetime.now(timezone.utc)
routine_ran = now.replace(hour=ROUTINE_HOUR_UTC, minute=0, second=0, microsecond=0)

if now < routine_ran:
    print("The routine has not read the file yet today. Nothing to check.")
    sys.exit(0)

age_hours = (routine_ran - built).total_seconds() / 3600
landed = fetches_before(routine_ran - timedelta(hours=LOOKBACK_HOURS), routine_ran)

print("routine read at  : " + routine_ran.isoformat())
print("items.json built : " + built.isoformat())
print("age it saw       : " + str(round(age_hours, 2)) + " h   (limit "
      + str(RENDER_LIMIT_HOURS) + ")")
print("items available  : " + str(items))
if landed is None:
    print("fetches in time  : unknown - could not read git history")
else:
    print("fetches in time  : " + str(len(landed)))
    for stamp in reversed(landed):
        print("                   " + stamp)

# ---- the alarm. Only these two conditions email you. ----

if age_hours > RENDER_LIMIT_HOURS:
    print("::error::NO BRIEF TODAY. items.json was " + str(round(age_hours, 1))
          + " hours old when the routine read it, past the "
          + str(RENDER_LIMIT_HOURS) + "-hour limit. No fetch landed in time and "
          + "render.py correctly refused to send yesterday's news as today's.")
    sys.exit(1)

if items == 0:
    print("::error::NO BRIEF TODAY. items.json was fresh but held zero items. "
          + "Every feed returned nothing - check whether the feed URLs moved.")
    sys.exit(1)

# ---- notes. These never email, because nothing is broken. ----

if landed is None:
    print("::warning::Could not read git history, so redundancy is unknown. "
          + "Check that the workflow sets fetch-depth on actions/checkout.")
elif len(landed) == 0:
    # items.json is fresh but no commit landed in the window. The likeliest
    # cause is a fetch that ran and found nothing changed, so it committed
    # nothing. Worth knowing, not worth waking up for.
    print("::warning::Fresh data, but no fetch commit landed in the last "
          + str(LOOKBACK_HOURS) + " hours. A run may have found no changes.")
elif len(landed) == 1:
    print("::warning::The brief went out on ONE successful fetch. The spare "
          + "did not land. One dropped run tomorrow means no brief.")

print("OK - " + str(items) + " fresh items, "
      + ("unknown" if landed is None else str(len(landed))) + " fetch(es) in time.")
