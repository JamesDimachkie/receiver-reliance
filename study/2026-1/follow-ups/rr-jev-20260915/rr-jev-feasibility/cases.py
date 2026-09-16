"""Explicit synthetic development cases. Labels never enter API state."""
from copy import deepcopy

FAMILIES = [
    dict(id="tests", source="The Atlas report records that all unit tests passed. One integration test failed.",
         claim="All Atlas unit tests passed.", reverse="The corrected Atlas report records that three unit tests failed. One integration test failed.",
         reword="Atlas unit testing finished with every test passing. Integration testing included one failure.",
         overclaim="All Atlas unit and integration tests passed.", overlabel="contradicts"),
    dict(id="stock", source="The warehouse count lists eight blue cases and no red cases in stock.",
         claim="Blue cases are in stock.", reverse="The revised warehouse count lists no blue cases and eight red cases in stock.",
         reword="Eight cases in the blue variant are available in the warehouse; the red variant has zero stock.",
         overclaim="The blue cases will arrive at the customer's address tomorrow.", overlabel="insufficient"),
    dict(id="schedule", source="The Cedar workshop is scheduled for Tuesday at 10:00. A remote attendance option has not been announced.",
         claim="The Cedar workshop is scheduled for Tuesday.", reverse="The Cedar workshop has moved to Thursday at 10:00; it will not take place on Tuesday.",
         reword="Cedar's workshop is on the calendar for 10:00 Tuesday. There is no announcement about remote attendance.",
         overclaim="The Cedar workshop supports remote attendance.", overlabel="insufficient"),
    dict(id="training", source="The training register lists Maya as having completed the introductory course. Maya has not completed the advanced course.",
         claim="Maya completed the introductory course.", reverse="The corrected training register lists Maya's introductory course as incomplete.",
         reword="Maya finished the introductory training course; the advanced course remains unfinished.",
         overclaim="Maya completed both the introductory and advanced courses.", overlabel="contradicts"),
    dict(id="maintenance", source="The maintenance log states that pump P2 passed its inspection. No inspection result is recorded for pump P3.",
         claim="Pump P2 passed inspection.", reverse="The corrected maintenance log states that pump P2 failed inspection.",
         reword="Inspection of P2 was completed with a passing result. P3 has no recorded inspection outcome.",
         overclaim="Pump P3 passed inspection.", overlabel="insufficient"),
    dict(id="backup", source="The run log states that the nightly backup completed. The restore test failed.",
         claim="The nightly backup completed.", reverse="The corrected run log states that the nightly backup did not complete.",
         reword="The nightly backup job finished successfully, but its restore test was unsuccessful.",
         overclaim="Both the nightly backup and its restore test succeeded.", overlabel="contradicts"),
]
TRANSITIONS = ("unchanged", "source_contradicts", "source_reworded", "claim_overstated",
               "purpose_changed", "revision_changed", "expired", "revoked")

def cases():
    result = []
    for family in FAMILIES:
        initial = dict(claim=family["claim"], source=family["source"], source_revision=1,
                       artifact_revision=1, purpose="PURPOSE_SUMMARY")
        for transition in TRANSITIONS:
            current = deepcopy(initial)
            label = "supports"
            if transition.startswith("source_"):
                current["source"] = family["reverse" if transition == "source_contradicts" else "reword"]
                current["source_revision"] = 2
                label = "contradicts" if transition == "source_contradicts" else "supports"
            elif transition == "claim_overstated":
                current["claim"] = family["overclaim"]
                current["artifact_revision"] = 2
                label = family["overlabel"]
            elif transition == "purpose_changed":
                current["purpose"] = "PURPOSE_INDEX"
            elif transition == "revision_changed":
                current["artifact_revision"] = 2
            result.append(dict(id=family["id"] + "__" + transition, family=family["id"],
                               transition=transition, initial=deepcopy(initial), current=current,
                               gold=label, may_reissue=(transition != "revoked"),
                               expected_initial_structural=(transition == "unchanged"),
                               expected_final_structural=(transition != "revoked")))
    return result
