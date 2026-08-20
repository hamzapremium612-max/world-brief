"""Step 3 of the daily brief: validate and render. NO AI in this file.

The agent hands back themes.json. This file does NOT trust it.

  - every item index is checked against the real list
  - an index that is invalid, or repeated, is dropped
  - any item the agent forgot lands in "Unsorted" rather than vanishing

That last guarantee is why this is code and not an instruction. A prompt can
ask a model not to lose a story. Only a loop can prove it did not.

Usage:  python render.py items.json themes.json brief.html
"""
import json
import sys
from datetime import datetime

# The visual language carries meaning, not decoration:
#   GREEN = sourced. Reporting, traceable to a link.
#   CLAY  = interpretation. The precedent. No source.
#   sans  = reporting        serif = interpretation
# Colour AND typeface both encode it, so the distinction survives greyscale,
# printing, or a reader who never consciously noticed the rule.
CSS = """
:root{--paper:#FBFAF8;--card:#FFF;--ink:#15181A;--soft:#5A6165;--faint:#8A9195;
--rule:#E4E2DD;--green:#1F5F4B;--green-wash:#EAF2EE;--clay:#9A5B33;
--clay-wash:#FAF1E9;--warn:#B3452B;--warn-wash:#FBECE8}
@media(prefers-color-scheme:dark){:root{--paper:#111314;--card:#181B1C;--ink:#E8EAEA;
--soft:#A2AAAC;--faint:#767E80;--rule:#282C2D;--green:#63BFA0;--green-wash:#14261F;
--clay:#D9976A;--clay-wash:#2A1D14;--warn:#E8836A;--warn-wash:#2E1A15}}
*{box-sizing:border-box}
html,body{overflow-x:hidden}
body{margin:0;background:var(--paper);color:var(--ink);overflow-wrap:break-word;
font-family:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;font-size:17px;line-height:1.62}
.wrap{max-width:640px;margin:0 auto;padding:34px 22px 72px}
.date{font-family:ui-monospace,Consolas,monospace;font-size:11.5px;letter-spacing:.16em;
text-transform:uppercase;color:var(--green);margin-bottom:14px}
h1{font-size:41px;line-height:1.02;letter-spacing:-.028em;margin:0 0 10px;font-weight:800}
.sub{color:var(--soft);font-size:15.5px;margin:0}
.hr{height:1px;background:var(--rule);margin:26px 0}
.glance{background:var(--green-wash);border-radius:10px;padding:16px 18px}
.glance .lbl,.warn .lbl,.kicker,.prec .lbl{font-family:ui-monospace,Consolas,monospace;
font-size:10.5px;letter-spacing:.14em;text-transform:uppercase}
.glance .lbl{color:var(--green);margin-bottom:9px}
.glance ol{margin:0;padding-left:19px;font-size:15px}
.glance li{margin:4px 0}
.warn{background:var(--warn-wash);border-left:3px solid var(--warn);border-radius:0 8px 8px 0;
padding:13px 15px;margin:16px 0;font-size:14.5px}
.warn .lbl{color:var(--warn);margin-bottom:5px}
.theme{margin-top:40px}
.kicker{color:var(--green);margin-bottom:7px}
h2{font-size:27px;line-height:1.17;letter-spacing:-.018em;margin:0 0 8px;font-weight:750}
.why{color:var(--soft);font-size:15px;margin:0 0 15px;font-style:italic}
.body p{margin:0 0 13px}
.srcs{display:flex;flex-wrap:wrap;gap:7px;margin-top:14px;min-width:0}
.srcs a{font-family:ui-monospace,Consolas,monospace;font-size:11px;text-decoration:none;
color:var(--green);border:1px solid var(--rule);border-radius:20px;padding:4px 11px;
background:var(--card);display:inline-block;max-width:100%;min-width:0;overflow:hidden;
text-overflow:ellipsis;white-space:nowrap}
.prec{background:var(--clay-wash);border:1px solid var(--rule);border-radius:10px;
padding:17px 19px;margin-top:20px}
.prec .top{display:flex;justify-content:space-between;align-items:baseline;gap:12px;
margin-bottom:9px;flex-wrap:wrap}
.prec .lbl{color:var(--clay);font-weight:700}
.prec .tag{font-family:ui-monospace,Consolas,monospace;font-size:10px;color:var(--clay);opacity:.85}
.prec .txt{font-family:Georgia,"Iowan Old Style",serif;font-size:16.5px;line-height:1.6;margin:0}
footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--rule);
font-family:ui-monospace,Consolas,monospace;font-size:11px;color:var(--faint);line-height:1.9}
"""


def esc(text):
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def validate(themes, item_count):
    """Trust nothing the agent handed back. Returns (clean_themes, warnings)."""
    warnings = []
    seen = set()
    clean = []

    for theme in themes:
        valid = []
        for n in theme.get("items", []):
            if isinstance(n, int) and 0 <= n < item_count and n not in seen:
                valid.append(n)
                seen.add(n)
        if valid:
            clean.append({
                "name": theme.get("name", "Untitled"),
                "why_it_matters": theme.get("why_it_matters", ""),
                "summary": theme.get("summary", ""),
                "pattern": theme.get("pattern"),
                "items": valid,
            })

    # A story the agent forgot is a story you never learn happened.
    missing = [n for n in range(item_count) if n not in seen]
    if missing:
        clean.append({
            "name": "Unsorted",
            "why_it_matters": "Not placed into a theme.",
            "summary": "",
            "pattern": None,
            "items": missing,
        })
        warnings.append(str(len(missing)) + " item(s) were not grouped and appear under 'Unsorted'")

    return clean, warnings


def render(data, themes, warnings, issue_no):
    built = datetime.fromisoformat(data["built_at"])
    items = data["items"]
    out = []
    add = out.append

    add('<!doctype html><html lang="en"><head><meta charset="utf-8">')
    add('<meta name="viewport" content="width=device-width, initial-scale=1">')
    add("<title>The Morning Brief - " + built.strftime("%d %b %Y") + "</title>")
    add("<style>" + CSS + "</style></head><body><div class=\"wrap\">")

    add('<div class="date">' + built.strftime("%A, %d %B %Y").upper()
        + " &middot; Issue " + str(issue_no).zfill(3) + "</div>")
    add("<h1>The Morning Brief</h1>")
    add('<p class="sub">World and Pakistan affairs, with the precedent behind them.</p>')
    add('<div class="hr"></div>')

    add('<div class="glance"><div class="lbl">At a glance</div><ol>')
    for theme in themes:
        add("<li>" + esc(theme["name"]) + "</li>")
    add("</ol></div>")

    # What this issue could not see. A document that admits its gaps is more
    # trustworthy than one that stays quiet about them.
    for w in warnings:
        add('<div class="warn"><div class="lbl">Incomplete coverage</div>' + esc(w) + "</div>")

    for theme in themes:
        add('<div class="theme">')
        add('<div class="kicker">' + str(len(theme["items"])) + " stories</div>")
        add("<h2>" + esc(theme["name"]) + "</h2>")
        if theme.get("why_it_matters"):
            add('<p class="why">' + esc(theme["why_it_matters"]) + "</p>")

        add('<div class="body">')
        for para in str(theme.get("summary", "")).split(chr(10)):
            if para.strip():
                add("<p>" + esc(para.strip()) + "</p>")
        add("</div>")

        add('<div class="srcs">')
        for n in theme["items"]:
            item = items[n]
            if item["link"]:
                add('<a href="' + esc(item["link"]) + '">' + esc(item["source"])
                    + " &middot; " + esc(item["title"][:30]) + "</a>")
        add("</div>")

        if theme.get("pattern"):
            add('<div class="prec"><div class="top"><div class="lbl">Precedent</div>')
            add('<div class="tag">interpretation &middot; not sourced</div></div>')
            add('<p class="txt">' + esc(theme["pattern"]) + "</p></div>")

        add("</div>")

    add("<footer>")
    add("Built " + built.strftime("%Y-%m-%d %H:%M UTC") + " &middot; " + str(len(items))
        + " items from " + str(len(data["feeds"])) + " feeds<br>")
    add("Sources: " + " &middot; ".join(data["feeds"]) + "<br>")
    add("Green = reported and linked. Clay = interpretation, no source.")
    add("</footer></div></body></html>")

    return "".join(out)


if __name__ == "__main__":
    items_path, themes_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    with open(items_path, encoding="utf-8") as f:
        data = json.load(f)
    with open(themes_path, encoding="utf-8") as f:
        raw_themes = json.load(f)
    if isinstance(raw_themes, dict):
        raw_themes = raw_themes.get("themes", [])

    themes, validation_warnings = validate(raw_themes, len(data["items"]))
    warnings = data.get("warnings", []) + validation_warnings

    html = render(data, themes, warnings, issue_no=1)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("wrote " + out_path)
    print("  " + str(len(themes)) + " themes, " + str(len(data["items"])) + " items")
    for w in warnings:
        print("  WARN: " + w)
