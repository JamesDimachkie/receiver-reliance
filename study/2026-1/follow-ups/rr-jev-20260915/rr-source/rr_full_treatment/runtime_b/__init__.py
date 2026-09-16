"""Implementation B of the RR study treatment source (arms U, S-all, R-all).

Importing this package is inert: it defines a name and a version string and
imports nothing else.  ``architecture.arm_isolation`` requires that importing
one arm never drags in another arm or the other accepted dependency, so the
arm modules are never imported from here.  A host chooses exactly one of
``rr_study_treatment_b.u``, ``rr_study_treatment_b.s`` or
``rr_study_treatment_b.r`` in a fresh process.
"""

AUTHORITY_ID = "RR-STUDY-TREATMENT-V6-SEMANTIC-AUTHORITY-DRAFT-1"
IMPLEMENTATION = "B"
