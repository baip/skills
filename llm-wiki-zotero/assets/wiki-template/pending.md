# Pending review

Pages whose synthesis must be re-checked against their sources. Items are added by
`zot.py changed --queue`, `zot.py stamp`, `review.py touched|since|restated`, or by hand. Resolve an item with
`review.py done PAGE --outcome O --basis TEXT [--cause ID]` only after re-reading the page against its sources;
the resolution is kept in reviewed.md. If that review changed the page, run `review.py touched PAGE` so its own
dependents are queued. `wikilint.py --strict` fails while items remain.

*(no open items)*
