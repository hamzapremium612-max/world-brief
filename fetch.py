"""Step 1 of the daily brief: gather the facts. NO AI in this file.

Everything here is deterministic on purpose. Freshness is arithmetic on a
timestamp, and arithmetic is right every single time. An AI asked to "only
use items from the last 36 hours" is right most days, and silent when it
is not - which is the exact bug this whole project exists to prevent.

Writes items.json for the agent to read.
"""
import json
import time
from datetime import datetime, timezone

import feedparser

NL = chr(10)

# Every feed here was TESTED before being written down. Al Jazeera and
# Reuters were dropped: both respond fine and return zero entries. A feed
# URL remembered rather than checked is how a brief quietly covers less of
# the world every day.
FEEDS = {
    "BBC World":      "https://feeds.bbci.co.uk/news/world/rss.xml",
    "Guardian World": "https://www.theguardian.com/world/rss",
    "Dawn":           "https://www.dawn.com/feeds/home",
    "Tribune":        "https://tribune.com.pk/feed/home",
}

MAX_ITEM_AGE_HOURS = 36     # an item older than this is not news
STALE_FEED_HOURS = 24       # if a feed's NEWEST item is older than this, it is behind
MAX_PER_FEED = 12           # ceiling, so one loud publisher cannot dominate


def hours_old(entry, now):
    stamp = entry.get("published_parsed") or entry.get("updated_parsed")
    if not stamp:
        return None             # no timestamp = freshness cannot be judged
    published = datetime.fromtimestamp(time.mktime(stamp), tz=timezone.utc)
    return (now - published).total_seconds() / 3600


def fetch_items():
    now = datetime.now(timezone.utc)
    items = []
    warnings = []

    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
        except Exception as error:
            warnings.append(source + ": could not be read - " + str(error))
            continue

        if not feed.entries:
            warnings.append(source + ": returned ZERO entries - the feed may be dead")
            continue

        # Is the FEED alive? A different question from whether an ITEM is fresh.
        # A publisher can break their feed and everything still looks normal.
        newest = hours_old(feed.entries[0], now)
        if newest is None:
            warnings.append(source + ": entries carry no timestamp - freshness unknown")
        elif newest > STALE_FEED_HOURS:
            warnings.append(source + ": newest story is " + str(round(newest))
                            + "h old - this feed is behind, its coverage may be missing")

        kept = 0
        for entry in feed.entries:
            if kept >= MAX_PER_FEED:
                break
            age = hours_old(entry, now)
            if age is None or age > MAX_ITEM_AGE_HOURS:
                continue
            items.append({
                "source": source,
                "title": entry.get("title", "(no title)"),
                "summary": (entry.get("summary", "") or "")[:400],
                "link": entry.get("link", ""),
                "hours_old": round(age, 1),
            })
            kept = kept + 1

    items.sort(key=lambda i: i["hours_old"])       # freshest first
    return items, warnings


if __name__ == "__main__":
    items, warnings = fetch_items()
    payload = {
        "built_at": datetime.now(timezone.utc).isoformat(),
        "feeds": list(FEEDS.keys()),
        "items": items,
        "warnings": warnings,
    }
    with open("items.json", "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=1, ensure_ascii=False)

    print("items.json written")
    print("  " + str(len(items)) + " fresh items from " + str(len(FEEDS)) + " feeds")
    for w in warnings:
        print("  WARN: " + w)
