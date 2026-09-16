"""Candidate exact arithmetic for the local estimation design.

This module performs no inference calls and imports no treatment or scorer.
Its probability interpretation is conditional on the separately specified
sampling, support and independence assumptions. It never declares efficacy.
"""
from __future__ import annotations

from fractions import Fraction
from math import factorial, isqrt


def ceil_fraction(value: Fraction) -> int:
    return -(-value.numerator // value.denominator)


def upper_root(value: Fraction, scale: int = 1_000_000) -> Fraction:
    """The smallest multiple of 1/scale whose square is at least value."""
    if value < 0 or type(scale) is not int or scale <= 0:
        raise ValueError("Nonnegative radicand and positive integer scale required")
    numerator = value.numerator * scale * scale
    denominator = value.denominator
    candidate = isqrt(numerator // denominator)
    if candidate * candidate * denominator < numerator:
        candidate += 1
    result = Fraction(candidate, scale)
    assert result * result >= value
    assert candidate == 0 or Fraction(candidate - 1, scale) ** 2 < value
    return result


def lattice_count(classes: int, target: Fraction, squared_mean_support: Fraction) -> int:
    """Equal two-task, three-topology cells for one population and one arm.

    Two arm means yield S=2*mean(support**2)/n. The candidate h**2=3*S
    law is eligible at the target exactly when n >= 6*mean(support**2)/h**2.
    At least one draw in every class/task/topology cell is required.
    """
    if type(classes) is not int or classes < 1 or target <= 0 or squared_mean_support <= 0:
        raise ValueError("Positive class count, target and support required")
    lattice = 6 * classes
    minimum = ceil_fraction(6 * squared_mean_support / (target * target))
    return lattice * max(1, ceil_fraction(Fraction(minimum, lattice)))


def contrast(strata: list[dict], *, scale: int = 1_000_000) -> dict:
    """Estimate R minus comparator from independent stratified samples.

    Each row supplies Fraction-compatible weight, lower/upper support and
    two nonempty lists: treatment and comparator. All counts are episodes.
    Missingness is rejected here; the instrument must resolve/record it first.
    Values may be integers or exact Fractions, never floating-point estimates.
    """
    if type(strata) is not list or not strata:
        raise ValueError("Nonempty list of strata required")
    total_weight = Fraction(0)
    estimate = Fraction(0)
    bound_sum = Fraction(0)
    contrast_support = Fraction(0)
    cells = []
    for row in strata:
        if type(row) is not dict:
            raise ValueError("Each stratum must be a record")
        weight, lo, hi = (Fraction(row[key]) for key in ("weight", "lower", "upper"))
        if weight <= 0 or lo > hi:
            raise ValueError("Invalid weight or support")
        samples = []
        for name in ("treatment", "comparator"):
            values = row[name]
            if type(values) is not list or not values or any(type(value) not in (int, Fraction) for value in values):
                raise ValueError("Nonempty exact episode values required")
            values = [Fraction(value) for value in values]
            if any(value < lo or value > hi for value in values):
                raise ValueError("Endpoint exceeds its prospective support")
            samples.append(values)
        left, right = samples
        delta = sum(left) / len(left) - sum(right) / len(right)
        contribution = weight * weight * (hi - lo) ** 2 * (
            Fraction(1, len(left)) + Fraction(1, len(right)))
        total_weight += weight
        estimate += weight * delta
        bound_sum += contribution
        contrast_support += weight * (hi - lo)
        cells.append({"treatment_n": len(left), "comparator_n": len(right),
                      "difference": delta, "S_contribution": contribution})
    if total_weight != 1:
        raise ValueError("Prospective stratum weights must sum exactly to one")
    radius_squared = 3 * bound_sum
    radius = upper_root(radius_squared, scale)
    return {"estimate": estimate, "S": bound_sum, "radius_squared": radius_squared,
            "radius_upper": radius,
            "lower": max(-contrast_support, estimate - radius),
            "upper": min(contrast_support, estimate + radius), "cells": cells}


def confidence_certificate() -> dict:
    """Exact conservative certificate for six predeclared two-sided intervals."""
    exp_lower = sum((Fraction(6 ** k, factorial(k)) for k in range(8)), Fraction(0))
    assert exp_lower > 256
    return {"exp_6_strict_lower": exp_lower, "directional_tail_strict_upper": Fraction(1, 256),
            "interval_count": 6, "simultaneous_coverage_lower": Fraction(61, 64),
            "scope": "Conditional candidate law; not an empirical or no-harm result"}
