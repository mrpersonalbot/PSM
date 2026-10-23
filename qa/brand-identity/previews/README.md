# Transparent PSM logo preview sheet

These previews are composites of the final RGBA asset candidates—not colored background rectangles. The asset artwork itself is identical in every panel.

- Header output: [`source/assets/psm-header-transparent.png`](../../../source/assets/psm-header-transparent.png), 3538×1297.
- Footer output: [`source/assets/psm-footer-transparent.png`](../../../source/assets/psm-footer-transparent.png), 1656×537 RGBA, derived from the corrected owner source `Logo/PSM Footer Corrected.png` (2000×2000 RGB, no source alpha, uniform near-black `#000001`).
- Preview panels are 1200×500. Site background colors were read in Chrome: header `rgba(255, 255, 255, 0.98)` (previewed over effective near-white `#FEFEFE`), footer `#151719`.

## Header — from `PSM White Background.png`

**White**

![Header logo on white](final/psm-header-preview-on-white.png)

**Black**

![Header logo on black](final/psm-header-preview-on-black.png)

**Website header background**

![Header logo on actual website header background](final/psm-header-preview-on-header.png)

**Website footer background**

![Header logo on actual website footer background](final/psm-header-preview-on-footer.png)

**Checkerboard transparency**

![Header logo on checkerboard](final/psm-header-preview-on-checkerboard.png)

## Footer — from `PSM Footer Corrected.png`

The corrected source preserves the blue PSM mark (`#0052A7` median), orange detail (`#FB6117` median), and near-white tagline (`#F6F6F7` median). The exact near-black matte (`#000001`) was verified along all four image edges. Matte removal estimates coverage against the measured source colors and unblends antialiased edges; the visible artwork was not redrawn, reconstructed, recolored, or resized. The crop retains 24 source pixels of transparent padding around the complete artwork.

**White**

![Footer logo on white](final/psm-footer-preview-on-white.png)

**Black**

![Footer logo on black](final/psm-footer-preview-on-black.png)

**Website header background**

![Footer logo on actual website header background](final/psm-footer-preview-on-header.png)

**Website footer background**

![Footer logo on actual website footer background](final/psm-footer-preview-on-footer.png)

**Checkerboard transparency**

![Footer logo on checkerboard](final/psm-footer-preview-on-checkerboard.png)
