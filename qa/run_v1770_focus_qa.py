from pathlib import Path
import sys
root=Path(sys.argv[1] if len(sys.argv)>1 else '.')
s=(root/'index.html').read_text(encoding='utf-8')
checks={
'version':'1.7.7.0' in s,
'inspection-dialog':'item-inspection-dialog' in s and 'showItemInspection' in s,
'gold-coin':'gold-coin-icon' in s and '${price} ◆' not in s,
'send-pointer':'pointerup' in s and 'touchend' in s,
'tavern-assets':'tavern-approach-v1770.webp' in s and 'tavern-door-v1770.webp' in s,
'asset-files':(root/'assets/scenes/tavern-approach-v1770.webp').exists() and (root/'assets/scenes/tavern-door-v1770.webp').exists(),
}
for k,v in checks.items(): print(('PASS' if v else 'FAIL'),k)
raise SystemExit(0 if all(checks.values()) else 1)
