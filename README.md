# GranCarb

**Description:** Attempt at a modern recreation of Carbdose, the application used by the EPA to aid with Radon mitigation in the 1990s. Will use wxPython to match, as closely as possible, the original layout of the Carbdose program.

**Antivirus Flags:** Doing this in Python using PyInstaller to generate an executable means that the resulting executable file is lacking a "paid commercial code-signing certificate." Windows Defender and corporate antivirus scanners may flag it as a false positive. The codebase is entirely open source for review.

## Goals

- Recreate each Carbdose screen (User input, Waste disposal, X-Protocol, Cancer risks, Gamma radiation, Bq<->Ci calculator) as closely as possible to the original 1990s layout.
- Reproduce the original calculations wherever the underlying formulas can be confirmed, and clearly flag anything that's approximated or unverified until it can be checked against the original tool.
- Keep the codebase readable and open so radon mitigation professionals, regulators, or hobbyist reviewers can inspect exactly how a result was produced.
- Package as a standalone Windows executable via PyInstaller so the tool doesn't require a Python install to run.

## Current State

- User input screen        (main entry screen)
- Waste disposal screen    (Pb-210 growth curve + pCi/g results)
- X-Protocol screen        (1-year GAC use, user-defined volume/density)
- Cancer risks screen      (stub - Non-Functional)
- Gamma radiation screen   (stub - Non-Functional)
- Bq <-> Ci calculator     (popup dialog - Non-Functional)

## Modeling Assumptions and Current Methodology

The original Carbdose source code and technical specification are not currently available. Where the underlying methodology could be inferred from established nuclear physics or the original application's behavior, those models have been reproduced. Where the original implementation could not be determined, reasonable engineering approximations or empirical calibration have been used and are documented below.

These assumptions are intended to be temporary until they can be verified against the original EPA/CDC methodology or reviewed by a subject matter expert.

### Radioactive Decay

The current implementation models Pb-210 ingrowth using the standard radioactive buildup equation:

```
λ = ln(2) / T½

Fraction of equilibrium = 1 − exp(−λt)
```

where:

- Pb-210 half-life = **22.3 years**
- `t` = elapsed time in years

This produces the exponential approach toward secular equilibrium.

### Decay Chain Simplification

The decay chain

```
Rn-222
→ Po-218
→ Pb-214
→ Bi-214
→ Po-214
→ Pb-210
```

is treated as effectively instantaneous compared with the 22.3-year half-life of Pb-210.

This allows the application to model only the slow ingrowth of Pb-210 bottleneck over time.

### Secular Equilibrium

After approximately one year, the application assumes:

```
Activity(Pb-210)
≈ Activity(Bi-210)
≈ Activity(Po-210)
```

Therefore the "Pb-210 plus progeny" calculation is approximated as

```
Total Activity = 3 × Pb-210 Activity
```

This reflects the expected secular equilibrium of the long-lived parent and its short-lived daughters.

### Water Treatment Model

The current implementation assumes:

- Constant influent radon concentration
- Constant water usage
- Constant GAC removal efficiency
- Continuous operation throughout the selected operating period
- Linear accumulation of captured activity

Captured activity is modeled as proportional to:

- influent activity
- water volume processed
- removal efficiency
- operating time

No breakthrough curve or adsorption kinetics are currently modeled.

### Geometry Assumptions

Two calculation methods are currently implemented:

- Uniform activity distributed throughout an entire 2 ft³ GAC column.
- Activity concentrated within the upper 5 inches of the GAC bed.

The current top-layer calculation assumes a 44-inch column height. This is an approximation and should be replaced once more accurate information is available.

### Density Assumptions

Current density values are:

- Wet GAC: **1.00 g/cm³**
- Dry GAC: **0.45 g/cm³**

User-defined density is also supported by the X-Protocol screen.

### Unit Conversions

The application prefers imperial gallons, and liters (when present) are a conversion.
The application currently uses standard accepted conversion constants:

- 1 gallon = 3.78541 liters
- 1 cubic foot = 28,316.846592 cm³
- 1 Curie = 3.7 × 10¹⁰ Becquerels
- 1 m³ = 1000 liters

### Known Placeholder

One calculation remains an empirical approximation.

The conversion from accumulated captured radon to total Pb-210 currently contains a calibration constant derived from matching known outputs of the original Carbdose software rather than from documented first-principles equations.

This calibration reproduces available reference cases but should be replaced once the original EPA/CDC calculation methodology is obtained.

## Future Verification

The following portions of the model should be reviewed with a subject matter expert:

- Original mathematical relationship between captured Rn-222 activity and resulting Pb-210 inventory.
- Intended treatment of adsorption and breakthrough over time.
- Official GAC column dimensions used by the original software.
- Original assumptions regarding activity distribution within the media.
- Default density values used by Carbdose.
- Any additional corrections, scaling factors, or engineering assumptions present in the original implementation.

## Acknowledgements

- The original **Carbdose** application and its underlying methodology, developed for the EPA in the 1990s to support radon mitigation via granular activated carbon (GAC) filtration.
- Built with [wxPython](https://www.wxpython.org/).
- Packaged with [PyInstaller](https://pyinstaller.org/).
- Markdown and Browser python libraries
- Icon used with permission of The Moose Party.

## License

Licensed under the [Apache License 2.0](LICENSE).

## Notice
Copyright 2026 Quinn Knowles

Licensed under the Apache License, Version 2.0
