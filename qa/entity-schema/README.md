# PSM business-entity JSON-LD correction

Baseline: `99923b72781c7f021a74f80b71f6ee13caaaa1e4` (main after PR #20).
Scope: homepage and `/toko-listrik-padang/` business nodes only. Product markup and visible product content remain unchanged.

## Before

The homepage identified the shop as `HardwareStore`, but had no stable `@id`, `url`, or `logo`. It also declared an unconfirmed short alias and social URLs as `sameAs`:

```json
{
  "@type": "HardwareStore",
  "name": "Pratama Sukses Mandiri",
  "alternateName": "Pratama",
  "legalName": "CV Pratama Sukses Mandiri",
  "sameAs": [
    "https://www.instagram.com/psm_padang/",
    "https://www.tiktok.com/@psm.padang"
  ],
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Jl. Ujung Belakang Olo No. 14e",
    "addressLocality": "Padang",
    "addressRegion": "Sumatera Barat",
    "addressCountry": "ID"
  }
}
```

The local Padang landing page used the undefined `ElectricalSupplyStore` type and had no stable `@id`, `url`, or `logo`:

```json
{
  "@type": "ElectricalSupplyStore",
  "name": "Pratama Sukses Mandiri",
  "legalName": "CV Pratama Sukses Mandiri",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Jl. Ujung Belakang Olo No. 14e",
    "addressLocality": "Padang",
    "addressRegion": "Sumatera Barat",
    "addressCountry": "ID"
  }
}
```

The old telephone field is omitted from these abbreviated examples. The generated site contains no `Organization` or `WebSite` nodes beyond the store entities described here.

## After

Both applicable pages now describe the same entity under one absolute, site-owned identifier. `HardwareStore` is the specific Schema.org store subtype verified for this electrical-supplies retailer (`Thing > Organization > LocalBusiness > Store > HardwareStore`).

```json
{
  "@context": "https://schema.org",
  "@type": "HardwareStore",
  "@id": "https://pratamasuksesmandiri.com/#business",
  "name": "Pratama Sukses Mandiri",
  "legalName": "CV Pratama Sukses Mandiri",
  "url": "https://pratamasuksesmandiri.com/",
  "logo": "https://pratamasuksesmandiri.com/assets/psm-header-transparent.png",
  "telephone": "+6281993399888",
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "Jl. Ujung Belakang Olo No. 14e",
    "addressLocality": "Padang",
    "addressRegion": "Sumatera Barat",
    "addressCountry": "ID"
  }
}
```

The same node retains the existing `hasMap` location URL. No Google Maps listing was added to `sameAs`. The unconfirmed `alternateName` and social `sameAs` values were removed pending owner confirmation. No registration identifier, new social link, or new website entity was introduced. The canonical logo asset is the existing PSM header artwork; its public URL returned HTTP 200 with `image/png` during this work.

## Owner review items

- Confirm whether “Pratama” is an established public alternate name and whether `@psm_padang` / `@psm.padang` are owner-controlled accounts before re-adding any of them to structured data.
- Confirm that `+62 819 9339 9888`, the telephone published by the current website, remains the authoritative business contact. The audit checkpoint records a different phone on the address-matching Maps profile; this change uses the website number and does not edit the profile.
- Confirm which Google Maps profile belongs to the business before adding a Maps URL to `sameAs`.
