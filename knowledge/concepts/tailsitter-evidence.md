---
id: tailsitter-evidence
concept: tailsitter
retrieved: 2026-11-11
---

# Do tailsitters work?

## Short answer
Yes, tailsitters have been built and flown, from 1950s military prototypes to present-day unmanned aircraft. The 1950s examples showed that hover and transition were achievable, but poor hover control, hard landings and the need for expert pilots led all of them to be dropped without production. Current evidence is mostly vendor claims, autopilot documentation and videos, so the sources do not show how reliably modern tailsitters transition or hold hover in wind.

## Evidence
| Example | Group (full-scale / commercial / research / hobby) | Year | Outcome | Main problem reported | Source |
|---|---|---|---|---|---|
| Convair XFY-1 Pogo | full-scale | 1954-1956 | Flew free flights and converted to horizontal flight; one aircraft built; program closed in 1955 after unresolved problems | Hard to slow after fast flight (no spoilers or air brakes); a May 1955 flight failed; landing required the pilot to look back over his shoulder | [Wikipedia](https://en.wikipedia.org/wiki/Convair_XFY_Pogo) |
| Lockheed XFV-1 Salmon | full-scale | 1954-1955 | Flew 32 flights, with a few in-flight transitions and a brief hover at altitude; full vertical operations never happened; cancelled June 1955 | Full VTOL tests waited on an engine that never arrived; temporary non-retractable landing gear; flyable only by very experienced pilots | [Wikipedia](https://en.wikipedia.org/wiki/Lockheed_XFV) |
| Ryan X-13 Vertijet | full-scale | 1955-1957 | Flew a full cycle on 11 Apr 1957: vertical takeoff from a trailer, horizontal flight, return to the trailer; retired Sept 1957 | unknown (source states no technical problems); Air Force saw no operational requirement | [Wikipedia](https://en.wikipedia.org/wiki/Ryan_X-13_Vertijet) |
| SNECMA Coléoptère | full-scale | 1958-1959 | Eight successful flights, including a hover demonstration; the ninth flight, meant to begin the move to horizontal flight, crashed and the pilot ejected; one built | Slow spin while hovering; landing controls not precise; dead-stick landing judged impossible; weak instrumentation and visual references on the final flight | [Wikipedia](https://en.wikipedia.org/wiki/SNECMA_Col%C3%A9opt%C3%A8re) |
| Shield AI V-BAT (ducted-fan tail-sitter per USNI) | commercial | 2024 | Vendor says operational with Ukraine's forces since Aug 2024; USNI describes it as fielded | unknown (source reports no problems; claims come from the vendor) | [Janes](https://www.janes.com/osint-insights/defence-news/air/shield-ais-v-bat-uas-operational-in-ukraine-since-august-2024), [USNI](https://www.usni.org/magazines/proceedings/2026/july/get-uavs-their-tails-and-fight) |
| WingtraRAY | commercial | unknown | Vendor sells it as a tailsitter survey drone; the page gives no independent performance data | unknown (vendor page names no tailsitter drawbacks) | [Wingtra](https://wingtra.com/vtol-drone/tail-sitter-vs-quad-plane/) |
| ArduPilot tailsitter support | hobby | unknown | Autopilot supports several tailsitter layouts with transition and hover tuning; the page reports no flight results | Prop strike when switching modes while disarmed; altitude gain in transition; throttle drop as the nose dips on some designs; pre-arm attitude errors | [ArduPilot docs](https://ardupilot.org/plane/docs/guide-tailsitter.html) |
| PX4 tailsitter frame | hobby | unknown | Supports duo and quad tailsitters; the docs say they are harder to tune and fly in hover and transition | Hover and transition difficulty, worse in wind | [PX4 docs](https://docs.px4.io/main/en/frames_vtol/tailsitter.html) |
| PX4 community builds (TBS Caipiroshka, ax1800) | hobby | unknown | Linked videos show takeoff, hover, transition and landing; no performance data given | unknown | [PX4 docs](https://docs.px4.io/main/en/frames_vtol/tailsitter.html) |
| Folk, hybrid UAV transition paper (arXiv 2412.06197) | research | 2024 | Modelling and control study of a small tailsitter; the first attempts at constant-altitude transition failed; flight testing not stated in the excerpt | Dynamically feasible transition is hard; no general, efficient control method with strong safety guarantees | [arXiv](https://arxiv.org/abs/2412.06197v1) |
| Blended Wing V1 tailsitter build log | hobby | unknown | Design rationale and steady CFD only; not flown | unknown (not flown) | [Hackaday](https://hackaday.io/project/179862/log/193071) |

## Recurring problems
- Hover and landing control were hard on early full-scale aircraft: Convair XFY-1 (landing needed a look over the shoulder), Coléoptère (spin in hover, imprecise landing controls), Lockheed XFV-1 (only very experienced pilots could fly it). Also reported for PX4 (harder to fly in hover) in the PX4 row.
- Transition was the hardest phase: Lockheed XFV-1 (few transitions only), Folk (constant-altitude transition attempts failed), PX4 (harder to tune in transition), ArduPilot (large altitude gain during transition).
- Limited pilot or operator view and instrumentation: Convair XFY-1 (landing view) and Coléoptère (lack of visual references and instruments). Only two rows, both from the 1950s.
- Wind sensitivity appears in only one row (PX4 tailsitter frame), so it does not meet the 2-row threshold. ArduPilot mentions wind only in passing, for belly landers.
- Cancellation for non-technical reasons: Convair XFY-1, Lockheed XFV-1, and Ryan X-13 were all ended partly because jets were faster or no operational requirement existed.

## What makes them work now
- Autopilot support for tailsitter modes: ArduPilot (dedicated tailsitter configuration, transition parameters, and gain scaling) and PX4 (tailsitter airframe type for duo and quad layouts). Both rows are from the autopilot docs.
- Fully autopilot-controlled transitions, with pilot input disabled during them: ArduPilot row.
- Airspeed-based gain scaling for hover control: ArduPilot row (the docs say it works best with an airspeed sensor).
- Choice of layout to suit the mission: PX4 row says quad layouts are easier to hover and more stable in wind, while duo layouts are more efficient in cruise.
- The USNI article attributes routine unmanned tailsitter landings to modern flight control systems. This is the author's claim, not a measured result, and it appears in the V-BAT/USNI row.

## Open questions for our designs
- Which layout (single, dual, quad, with or without control surfaces) gives adequate hover control in our target wind conditions? The PX4 and ArduPilot docs point in different directions.
- Where is an independent flight-test record of transition success rates for small tailsitters? The sources found here are design papers, vendor claims and videos.
- Does our landing method need a belly or tail landing, given that ArduPilot notes belly landers handle wind better and that some designs need a large tilt throw to take off?
- What pilot or observer visibility do we need during transition and landing? The 1950s sources flag visibility as a risk, but no modern source addresses it.

## Gaps in this search
- Two research PDFs (University of Washington and Chalmers) could not be fetched, so no flight-test data from them is included.
- The ArduPilot forum thread on dual-motor tailsitters appeared in search results but was not opened.
- Airbound and the other delivery companies from the DroneLife tag page were not included, because that page did not say whether they fly tailsitters.
