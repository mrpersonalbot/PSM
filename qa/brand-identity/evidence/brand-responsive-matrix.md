# PSM Brand Identity Responsive QA

- Commit under test: `5a873f26a937d82ada000be1916b77cd9d15d1f8`
- Browser: `Google Chrome 156.0.8078.48` via Chrome DevTools Protocol; no new packages installed.
- Responsive cases: `36/36` passed; `0` failed.
- Production baseline (before): `https://pratamasuksesmandiri.com/` captured at 320×740 and 1280×900.
- Logo click to homepage: `True`.
- Computed backgrounds: `{'header': 'rgba(255, 255, 255, 0.98)', 'footer': 'rgb(21, 23, 25)'}`.
- Matrix covers home, local store, B2B procurement, retailer partnership, product detail, contact at widths 320, 360, 390, 430, 768, 1280; mobile DPR=2 through 430px.

| Route | 320 | 360 | 390 | 430 | 768 | 1280 |
|---|---:|---:|---:|---:|---:|---:|
| home | PASS | PASS | PASS | PASS | PASS | PASS |
| local-store | PASS | PASS | PASS | PASS | PASS | PASS |
| b2b | PASS | PASS | PASS | PASS | PASS | PASS |
| retailer | PASS | PASS | PASS | PASS | PASS | PASS |
| product | PASS | PASS | PASS | PASS | PASS | PASS |
| contact | PASS | PASS | PASS | PASS | PASS | PASS |

## Screenshots

- Before/after homepage and footer screenshots are stored in this directory.
- Per-case metrics, resource results, and console/network evidence are in `brand-responsive-matrix.json`.
