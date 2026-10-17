# PSM Mobile Conversion Optimization — verification record

**Verification date:** 2026-10-18 (WIB)
**Status:** Final local verification passed; merge and production deployment remain pending.

## Repository and PR base

- Release branch: `fix/psm-mobile-conversion-ux`, created from fetched `origin/main` at `ca6b3453378c1331e011e334332864a4526004a3`.
- The original worktree HEAD, `bc674f02b5b68de88925973e5035be3db568803d`, is an ancestor of that main base; no Local SEO commit was duplicated.
- Before switching branches, the mobile-only changes were saved in a recoverable local stash and restored onto the release branch. The backup is retained locally and excludes `Logo/`.
- The unrelated untracked `Logo/` directory was left untouched and is not part of the mobile change set.
- Marketing SEO repository was not modified.

## Final implementation

Scope remains limited to the accepted homepage hero, `/toko-listrik-padang/` hero, and `/kontak/` mobile action dock.

- `build.py` applies route-specific body markers to Padang and contact pages and versions the human-touch CSS URL with `?v=pratama-mobile-ux-1`.
- `source/human-touch.css` reflows the homepage and Padang hero at narrow widths, allowing headings/copy to wrap and retaining accessible full-width actions. The contact dock is placed in document flow on mobile, after page content, rather than fixed over content; its bottom margin includes `env(safe-area-inset-bottom)`.
- Existing CTA labels, WhatsApp/Maps/catalog destinations, floating WhatsApp action, business information, and desktop styles were not intentionally changed.

## Build and regression tests

- `python3 build.py` — **passed**; generated 797 HTML pages from 757 products. Image audit summary: 11 matched, 746 held for review.
- `python3 -m unittest discover -s tests -v` — **12 tests passed**, 0 failures.
- `python3 -m compileall -q build.py tests` — passed.
- Ruff 0.17.1 — checked `build.py` and `tests/test_mobile_ux.py`: 20 findings in `build.py` match findings from `HEAD`'s version of that file; **0 new findings** and **0 findings in the new mobile test**. Existing findings were not refactored as part of this task.
- `git diff --check` — passed.

## Browser and accessibility verification

- **59 browser cases:** 56 mobile viewport/scroll cases and 3 desktop cases.
- Mobile routes: `/`, `/toko-listrik-padang/`, `/kontak/`.
- Widths: 320, 360, 390, 430 CSS px. Portrait height: 800 CSS px. Landscape heights: 240, 259, 281, 310 CSS px respectively.
- Tested top and bottom scroll positions on all routes and the middle position on contact. **No matrix failures:** no horizontal document overflow, target hero heading/action clipping, or contact dock/content overlap; contact overlap count was 0 across tested positions/orientations. At 1440×900, all three routes had no horizontal overflow and the mobile dock was hidden.
- Keyboard: eight Tab presses reached the homepage “Tanya Produk” WhatsApp link; it matched `:focus-visible` with a 3px solid outline.
- Safe-area simulation: Chromium DevTools emulated a 34px bottom inset on `/kontak/` at 320×800. `env(safe-area-inset-bottom)` computed to 34px; dock bottom margin computed to 44px; at document bottom the dock ended at y=756, leaving 44px to the viewport edge, and overlapped no page content. Document width remained 320px.
- Local HTTP returned 200 for `/`, `/toko-listrik-padang/`, `/kontak/`, and `/assets/human-touch.css?v=pratama-mobile-ux-1`.

## SEO, business data, and action links

- Homepage, Padang, and contact output retained title, description, canonical, Open Graph, Twitter-card metadata, and parseable JSON-LD.
- The homepage `HardwareStore` and Padang `ElectricalSupplyStore` entities are present. Padang JSON-LD and visible page output contain the approved address, official Google Maps URL, weekday hours 09:00–18:00, Saturday 09:00–17:00, and no Sunday opening hours. Contact visible address, hours, and Maps URL were also checked.
- Contact output contains breadcrumb JSON-LD, not a LocalBusiness entity; no contact-store entity was asserted. No SEO/business source files were modified.
- Generated homepage, Padang, and contact actions retain their existing targets. No real WhatsApp inquiry was sent and external destinations were not opened.

## Screenshots

All listed files are 320×800 PNGs.

- Homepage: `before-home-320x800.png`, `after-home-320x800.png`
- Padang: `before-padang-320x800.png`, `after-padang-320x800.png`
- Contact bottom: `before-contact-bottom-320x800.png`, `after-contact-bottom-320x800.png`
- Contact top: `after-contact-top-320x800.png`
- `reconstructed-before-contact-top-320x800.png` is explicitly a *reconstruction*: the former fixed-dock positioning was reapplied in the browser after implementation to illustrate the top-of-page overlap. It is not represented as a screenshot captured before the edit.

## Change-set boundary and limitations

- Intended PR files: `build.py`, `source/human-touch.css`, `tests/test_mobile_ux.py`, `evidence/mobile-ux/test-record.md`, and the eight listed screenshots.
- No generated `dist/` output or unrelated application/data files are included. `Logo/` remains untouched and is excluded from the PR.
- Safe-area behavior was tested with Chromium emulation, not a physical iPhone or Safari. No production deployment, live conversion analytics, or real external inquiry was tested; no conversion lift is claimed.
- The mobile release is prepared from the current `origin/main` base. The recovery stash remains available locally; the change set is for a focused PR only. Merge and production deployment remain pending owner approval.
