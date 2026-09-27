# The Briar Crown v1.7.9.2 — Playable Heroes & Daylight Foundations

- Six class choices now have distinct persistent visual identities: Knight, Ranger, Wizard, Rogue, Druid, and Bard.
- Character selection uses the approved class portraits rather than emoji-only cards.
- The selected class portrait follows the player into the live HUD and Skills view while the custom player name remains independent.
- Older saves migrate safely: the stored class selects the matching visual identity without changing the player's name or progress.
- Adds explicit scene-lighting metadata so exterior daylight, warm daytime interiors, stained-glass chapel light, underground darkness, misty Moonfen, and magical Moonwell lighting are authored rather than accidental.
- Chapter One remains late-morning/daylight unless gameplay explicitly advances time; crypts, cellars, and tunnels remain naturally dark.
- Adds optional class-specific approaches without removing the shared solutions: Knight can force the discovered tavern cellar hatch, Ranger can read tracks on Chapel Road, Druid can listen to the old yew in the chapel yard, Rogue retains its lockpicking advantage, Wizard retains Moonwell attunement, and Bard retains the tavern duet route.
- This release establishes the rendering/data foundation for later full-body character overlays and scene-family replacements without baking one hero into shared background art.

## v1.7.9.2.4 — Scene Family One: Tavern Door Focus
- Added `assets/scenes/tavern-door-v17924.webp`, a focused crop derived from the approved v17922 Briar Lantern exterior; no new/generated artwork.
- Rebound `tavernDoor` to the dedicated focus plate and aligned its Door/Square hotspot geometry to the new framing.
- Bumped build/cache/release metadata to build 17924 and added an explicit tavern-door smoke-test contract.
- Existing story logic, tavern interior directional views, chapel/cemetery work, class paths, and save schema remain unchanged.
