# Review ledger

Append-only record of resolved review items (AGENTS.md §4), written by `review.py done`. Each line gives the
date, the outcome, the cause that was reviewed, the pages, and the basis for the outcome:

* *corrected*: the page was changed to fit the revised evidence (and reported with `review.py touched`);
* *unchanged*: the page uses the revised content, was re-read against it, and still holds;
* *not-affected*: the page depends on the changed page, but not on the part that changed.

A (page, cause) recorded here is never queued again. A new revision of the cause is a new cause.

