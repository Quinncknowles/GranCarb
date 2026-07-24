"""
gac_physics.py

Pure physics/math for the GAC Radon Removal Calculator.
No GUI dependencies -- this file only needs the standard library.

STATUS: None of the calculations below have been checked or approved by
a subject matter expert. The goal is to model the known Rn-222 decay
chain where possible, and otherwise to reproduce the reference outputs
of CARBDOSE (an existing tool) using similar formulas. See individual
function docstrings for what is physics-derived vs. curve-fit.
"""

import math


# ===========================================================================
# Bq <-> Ci unit conversion
# ===========================================================================
# Plain unit-definition constants, not model assumptions.

BQ_PER_CI = 3.7e10      # exact definition: 1 Curie = 3.7e10 Becquerel
M3_TO_LITERS = 1000.0   # 1 cubic meter = 1000 liters

# Metric prefixes available for each unit, mapped to their power-of-ten
# exponent. "(none)" is the base unit (Bq or Ci with no prefix).
SI_PREFIXES = [
    ("p (10^-12)", -12),
    ("n (10^-9)", -9),
    ("u (10^-6)", -6),
    ("m (10^-3)", -3),
    ("(none)", 0),
    ("k (10^3)", 3),
    ("M (10^6)", 6),
    ("G (10^9)", 9),
    ("T (10^12)", 12),
]


# ===========================================================================
# Volume / unit conversions
# ===========================================================================

GALLONS_TO_LITERS = 3.78541
CUFT_TO_CM3 = 28316.846592
TWO_CUFT_CM3 = 2 * CUFT_TO_CM3  # homogeneous-distribution column volume

# PLACEHOLDER GEOMETRY -- flag for SME review.
# Assumes a ~44" tall 2 cu ft column, and that the "waste disposal" case
# only cares about the top 5" layer of media. Replace with real column
# geometry when available.
LAYER_VOLUME_FRACTION = 5.0 / 44.0
LAYER_VOLUME_CM3 = TWO_CUFT_CM3 * LAYER_VOLUME_FRACTION


# ===========================================================================
# Pb-210 ingrowth model
# ===========================================================================
# MODEL NOTES (read this before the two functions below):
#
# Rn-222 captured on GAC decays through a chain of very short-lived progeny
# (Po-218, Pb-214, Bi-214, Po-214 -- all well under an hour half-life) down
# to Pb-210, which is effectively long-lived (half-life = 22.3 years) by
# comparison. So on a "years" timescale, the chain above Pb-210 is treated
# as instantaneous, and the interesting slow process is the *ingrowth* of
# Pb-210 itself, which follows the standard buildup curve:
#
#     fraction_of_equilibrium(t) = 1 - exp(-lambda_Pb210 * t)
#     lambda_Pb210 = ln(2) / 22.3 (per year)
#
# Pb-210 itself decays to Bi-210 (t1/2 = 5.01 days) then Po-210
# (t1/2 = 138.4 days) then stable Pb-206. Both of those half-lives are
# tiny next to a year, so within about a year of Pb-210 being present,
# Bi-210 and Po-210 reach *secular equilibrium* with it -- meaning their
# activities become essentially equal to the Pb-210 activity. That's why
# "Growth of Pb-210 plus Bi-210 and Po-210 progeny" is modeled below as
# 3x the Pb-210-only activity (one full chain of three progeny in
# secular equilibrium), not something invented arbitrarily.

PB210_HALFLIFE_YEARS = 22.3
PROGENY_MULTIPLIER = 3.0  # Pb-210 + Bi-210 + Po-210 at secular equilibrium


def pb210_growth_fraction(years: float) -> float:
    """
    Fraction of equilibrium Pb-210 activity reached after `years` of
    ingrowth. Physics-derived (standard radioactive buildup curve) --
    see MODEL NOTES above.
    """
    lam = math.log(2) / PB210_HALFLIFE_YEARS
    return 1 - math.exp(-lam * years)


def total_pb210_pci_at_equilibrium(activity_pci_per_l, volume_val, unit,
                                    efficiency_percent, days):
    """
    Total Pb-210 activity (pCi) that will eventually grow in, based on the
    radon activity captured by the GAC bed over the stated operating
    period.

    NOT purely first-principles -- see CALIBRATION_CONSTANT note below.
    """
    volume_l = volume_val if unit == "Liters" else volume_val * GALLONS_TO_LITERS
    daily_removed_pci = activity_pci_per_l * volume_l * (efficiency_percent / 100.0)
    return (daily_removed_pci * days) / CALIBRATION_CONSTANT
    
# ===========================================================================
# Waste classification thresholds (pCi/g)
# ===========================================================================
# PCI_PER_G_YELLOW_THRESHOLD / PCI_PER_G_RED_THRESHOLD -- flag for SME review.
#
# These mark where a Pb-210 pCi/g reading moves from "green" (ok) to
# "yellow" (caution) to "red" (concern) in the waste disposal screen:
#   value > PCI_PER_G_RED_THRESHOLD      -> red
#   value > PCI_PER_G_YELLOW_THRESHOLD   -> yellow
#   otherwise                            -> green
#
# TODO: Origin of these two specific numbers (1000 / 2000 pCi/g) is not
# documented in the source this was built from. They may reflect a
# regulatory disposal limit, a CARBDOSE convention, or an arbitrary
# round-number choice -- unconfirmed. Needs SME sign-off before this
# is used for any real classification decision.
PCI_PER_G_YELLOW_THRESHOLD = 1000
PCI_PER_G_RED_THRESHOLD = 2000
 


# CALIBRATION_CONSTANT -- flag for SME review.
# Fit against two known reference outputs from the CARBDOSE Waste Disposal
# screen, both at "Selected time = 100 years" and the "5 inch layer" method:
#   activity=900,    12 gal, eff=95%, 30 days -> Total Pb-210 = 2.06E+05 pCi, 31.99 pCi/g
#   activity=120000, 12 gal, eff=90%, 30 days -> Total Pb-210 = 2.60E+07 pCi, 4040.70 pCi/g
# A plain "activity * volume * efficiency * days" formula overshoots both
# of those by a consistent ~5.4x, so this constant divides that out.
# TODO: This is a curve fit to two examples, NOT derived from a
# first-principles radon/GAC mass-balance model. Needs a 3rd reference
# point (ideally from different conditions) to validate before trusting
# it outside the fitted range.
CALIBRATION_CONSTANT = 5.4056