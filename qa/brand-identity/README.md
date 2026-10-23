# PSM Brand Identity — QA & Asset Provenance

## Baseline and release boundary

- Verified base / `origin/main`: `5a873f26a937d82ada000be1916b77cd9d15d1f8`.
- PR #19 is merged at this SHA. The `Build and publish Pratama site` run `39739980079` and GitHub Pages run `39739980111` both completed successfully; Pages `build` and `deploy` jobs succeeded. The production site was captured before this change.
- This feature branch is based on that verified, deployed baseline. This task has not merged or deployed anything.
- The original `/Users/openclaw/PSM` checkout and its staged, unstaged, and untracked files (including `Logo/`) remain untouched. Both original logo PNGs and the newly supplied corrected footer PNG are unchanged.

## Owner-supplied image inventory

- Header source `Logo/PSM White Background.png`: 4000×4000, 8-bit RGB PNG with no alpha. Its canvas is near-white (predominantly `#FEFEFE`, with near-white antialiased variations). Main artwork samples include navy/blue `#013E7F`, orange `#F96E2B`, and dark tagline `#1F3040`.
- Original footer source `Logo/PSM Black Background.png`: 4000×4000, 8-bit RGB PNG with no alpha. Its actual canvas is white (`#FFFFFF` at inspected corners), despite the filename; it remains preserved and was not used for the final footer.
- Corrected footer source `Logo/PSM Footer Corrected.png`: 2000×2000, 8-bit RGB PNG with no alpha. The solid background is near-black `#000001`, verified on all four edges. Measured median artwork colors are blue `#0052A7`, orange `#FB6117`, and near-white tagline `#F6F6F7`.

The source files were left unchanged. The new footer extraction keys the verified `#000001` matte, estimates antialias coverage against the measured blue/orange/tagline colors, and unblends edge RGB to prevent a black fringe on the site footer. No artwork was redrawn, reconstructed, or stretched. The header uses its already-approved extraction and remains byte-identical (SHA-256 `d14a392d68b50882cb6638e2bc9308589d3fdbe2dae41442153aa355f752b6cd`). The header crop retains its prior 64px source padding; the corrected footer crop retains 24px source padding.

## Generated transparent assets

- `source/assets/psm-header-transparent.png` — 3538×1297, 8-bit RGBA PNG.
- `source/assets/psm-footer-transparent.png` — 1656×537, 8-bit RGBA PNG, from the corrected footer source.
- Both output files have genuine alpha: all four canvas corners are alpha 0; representative logo-core samples are effectively opaque, and the tagline remains present. Preview composites on white, black, website header, website footer, and checkerboard are in `previews/README.md` and `previews/final/`.
- The build copies these canonical PSM assets into `dist/assets`; it does not read the local `Logo/` folder.

### Corrected footer visual review

The replacement source has a genuine solid near-black canvas and an intact white tagline. It was unblended into true RGBA without rebuilding the lettering. Final composites on white, black, the actual website footer color, and checkerboard were visually inspected: the tagline remains complete and readable on the dark footer; no visible matte fringe, missing stroke, rough tagline texture, background remnant, or proportion change was found. White-on-white is intentionally low-contrast in the white-background diagnostic preview; the logo is intended for the dark footer. The owner has reviewed and approved the final header and footer previews. That approval permits commit, push, and PR preparation only; merge and production deployment remain prohibited.

## Website integration

- Header: the new PSM artwork is at the upper-left, links to `/`, has accessible name/alt `Pratama Sukses Mandiri`, and retains the existing desktop/mobile navigation. CSS uses `object-fit: contain`; Chrome rendered the logo at 210×60px on 320px mobile and 260×74px on desktop. No navigation overlap was detected.
- Footer: the footer-specific PSM artwork is used against the dark footer; Chrome rendered it at 260×84.3px on both 320px mobile and desktop. Its tagline remains readable at that actual size, and `CV Pratama Sukses Mandiri` remains visible as legal identity.
- Public generated HTML no longer contains the retired exact brand string. Organization/store/brand/breadcrumb names and relevant social brand metadata use `Pratama Sukses Mandiri`; `legalName` stays `CV Pratama Sukses Mandiri`. Product-page `<main>` content, Product JSON-LD, product titles, routes, canonical URLs, and robots directives are preserved. Only the retired brand phrase in applicable meta descriptions is substituted; the remaining description text and intent are unchanged.
- The existing GitHub Pages workflow has fixed assertions on legacy header/footer asset URLs and a legacy CSS URL. To honor the explicit no-workflow-change constraint, those header/footer URLs are retained as byte-identical compatibility aliases of the new PSM assets. The canonical `psm-*-transparent.png` files are also shipped in `dist/assets`. `.github/workflows/pages.yml` is unchanged and its path assertions pass. The old `pratama-logo-white.svg` CSS URL remains only in the workflow-pinned inactive `.footer-brand:before` rule; generated HTML no longer contains that class or references the old SVG logo.

## Regression and responsive verification

- `python3 build.py`: passed — 797 HTML pages generated from 757 products.
- `python3 -m unittest discover -s tests -v`: 29 tests passed, including 6 new brand/logo tests for true RGBA assets, compatibility paths, homepage link/accessibility, footer legal name, public brand, social metadata, and structured data.
- Regression comparison against a clean base build: 757 product routes; 94 noindex product variants; 702 unique sitemap URLs. Product main content, Product JSON-LD, and product titles changed in 0 routes; no unrelated product-meta-description copy changed. `robots.txt`, WhatsApp destinations, and Google Maps links are unchanged.
- Direct artifact audit: all 757 product route files are present; 94 product variants remain noindex; all 702 unique sitemap entries resolve to existing self-canonical indexable pages. All 797 generated HTML pages carry the new public site name and CV legal footer, with zero retired-brand occurrences.
- Pages workflow path assertions: passed; `.github/workflows/pages.yml` diff is empty.
- Real Chrome 156.0.8078.48 / CDP: 36/36 route×viewport cases passed for homepage, local store, B2B procurement, retailer partnership, affected product detail, and contact at 320, 360, 390, 430, 768, and 1280 CSS px. Mobile cases through 430px used DPR2; screenshots include final home and footer views at 320×740 and 1280×900 plus an extra 320px DPR2 capture. Header logo link click-to-home passed. All logos/images loaded, no horizontal overflow or logo/hamburger overlap, and there were 0 console-error cases and 0 failed network requests.
- Matrix details: `evidence/brand-responsive-matrix.md` and `evidence/brand-responsive-matrix.json`.

## Before/after screenshots

Production-before and local-after screenshots are stored under `evidence/`:

- Homepage mobile: `before-home-320x740.png`, `after-home-320x740.png`.
- Homepage desktop: `before-home-1280x900.png`, `after-home-1280x900.png`.
- Footer mobile: `before-footer-320x740.png`, `after-footer-320x740.png`.
- Footer desktop: `before-footer-1280x900.png`, `after-footer-1280x900.png`.
- DPR2 mobile header: `after-home-320x740-dpr2.png`.

Physical iOS/Safari testing was not performed. No merge or production deployment was performed or authorized.
