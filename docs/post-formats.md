# Post Formats

Gitcast generates 4 post formats from a single capture.

## Deep Tech

* **Audience:** Developers on X/Twitter
* **Length:** 200-260 characters
* **Style:** Technical precision, specific function names, before/after code, sharp insight

**Best for:** Algorithm improvements, architecture decisions, performance wins, interesting bugs

*Example output:*
"Replaced O(n²) nested loop with a hash map lookup in `build_payload()`. OCR confidence jumped 3.1% — turns out the bottleneck was duplicate key scanning, not the OCR itself. One dict, problem gone."

## The Struggle

* **Audience:** Build-in-public community
* **Length:** 220-280 characters
* **Style:** Opens with frustration, walks through failed attempts, lands on the fix, ends with a question

**Best for:** Debugging sessions, things that took longer than expected, moments of "it was one line"

## Quick Win

* **Audience:** General developer feed
* **Length:** 140-200 characters
* **Style:** Outcome first, one sentence context, one sentence forward momentum

**Best for:** Feature shipped, test passing, deploy done

## LinkedIn Post

* **Audience:** Professional network
* **Length:** 800-1300 characters
* **Style:** Hook line 1, story middle, CTA end, line breaks for readability

**Best for:** Weekly build updates, lessons learned, milestone announcements

## PR Description

* **Audience:** Code reviewers on GitHub
* **Format:** Structured markdown
* **Sections:** What changed, Why, How, Testing, Notes

**Best for:** Any pull request where you want to explain context beyond just what the diff shows
