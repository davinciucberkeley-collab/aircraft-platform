---
id: std-astm-f3298-lightweight-uas
title: ASTM F3298 Standard Specification for Design, Construction, and Verification of Lightweight Unmanned Aircraft Systems (UAS) (version 19 copy)
authors: ASTM International
year: 2019
url: https://cdn.standards.iteh.ai/samples/102606/1efc8a6cc1c646a5bd9ad4d8e58eb106/ASTM-F3298-19.pdf
type: standard
retrieved: 2026-11-11
verified: true
---

## Summary
Consensus standard for the airworthiness design of light UAS, covering fixed-wing and VTOL aircraft. It sets a default scope of 55 lb or less and gives a 1.5 ultimate factor for limit load cases. It covers landing loads qualitatively but gives no landing load factor in the text read. The URL is a third-party sample copy of ASTM F3298-19; a newer revision (F3298-24) exists.

## Usable rules / numbers
- [landing_load_factor] No numeric landing load factor found. Landing and ground loads are defined and required to be carried without damage, but magnitudes are not in the sections read (sections 3.1.33.2 to 3.1.33.4, 7.5.1.3, 7.10.5.1).
- [landing_load_factor] Symbols n, n1, n2, n3 (wheel load factor) are defined; no values given in the read sections (sections 3.2.21 to 3.2.24).
- [landing_load_factor] Ultimate load equals limit load times a factor of safety; the definition uses a heuristic 1.5, and section 7.8.1 fixes the limit-load check at 1.5 (sections 3.1.33.7, 7.8.1).
- [landing_load_factor] Scope: applies to UA under 55 lb (25 kg) maximum takeoff gross weight by default, but is not strictly limited to that weight (sections 4.2.1, 1.3).

## How we could use it
- Use 1.5 ultimate factor and 55 lb scope as the regulatory anchor for structure checks. The standard does not confirm the 3 g landing load factor.
- Check the F3298-24 revision for any numeric load factor before relying on the 3 g value.
