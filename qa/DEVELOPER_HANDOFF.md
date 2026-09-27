# The Briar Crown 1.7.9.0 — developer handoff

Development master: the newest FULL v1.7.9.1 package. Do not branch future work from
an update-only or older ZIP.

## Visual baseline

Chapter One visual continuity is considered source-complete for this release:
- above-ground flagged night/dusk scenes have daylight replacements;
- tavern directional views are distinct coordinated assets;
- Rowan review locations use the locked red-tunic/green-trouser language;
- major solved/collected scene states have explicit visual variants;
- all 41 canonical items have dedicated inspection art.

`qa/scene-review.json` locks image path, image hash, hotspot hash, description hash,
and object-position metadata for 93 room/view/state records. Any scene or hotspot
change must intentionally update that review after full-location inspection.

## Release gates

Latest component results:
- `qa/run_qa.py`: 572/572
- `qa/run_stabilization.py`: 191/191
- `qa/run_consistency.py`: 119/119
- `qa/run_cleanup_smoke.py`: 35/35
- `qa/run_cleanup_safety.py`: 9/9
- `qa/check_release.py`: 16/16
- `qa/run_story_paths.py`: 12/12 class-ending journeys

The all-in-one runner can take several minutes because browser suites launch
sequentially; CI should run `python qa/run_all.py .` with a normal job timeout.

## Remaining external validation

Automated fixtures do not certify Safari/Home-Screen persistence, live service-worker
installation/update, or iOS keyboard behavior. Run the START-HERE device smoke test
after deployment without clearing site data.
