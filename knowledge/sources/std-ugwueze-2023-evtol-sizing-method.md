---
id: std-ugwueze-2023-evtol-sizing-method
title: An Efficient and Robust Sizing Method for eVTOL Aircraft Configurations in Conceptual Design
authors: Osita Ugwueze, Thomas Statheros, Nadjim Horri, Michael A. Bromfield, Jules Simo
year: 2023
url: https://knowledge.lancashire.ac.uk/id/eprint/46106/1/aerospace-10-00311-v2.pdf
type: paper
retrieved: 2026-11-18
verified: true
---

## Summary
Peer-reviewed conceptual sizing method for eVTOL configurations (Aerospace 2023, 10, 311). It sets a motor power margin for emergency power, and defines a landing gear design load factor without giving its value. It gives no thrust-to-weight ratio.

## Usable rules / numbers
- [hover_thrust_to_weight_min] None for thrust-to-weight. Section 3.4, Eq. 18 and Table 2: motor power margin PM = 50%, to provide emergency power after a motor failure. This is a power margin, not a thrust margin. The paper compares it with helicopter power margins of about 30% (ref. [21]).
- [landing_load_factor] None. Section 3.3, Eq. 17 defines a landing gear design load factor (eta_lg), but the paper gives no numerical value for it.

## How we could use it
- The 50% power margin is a different quantity and should not be used to set the thrust-to-weight rule.
- Confirms that a landing gear load factor exists as a sizing parameter in eVTOL work, but gives no number to use.
