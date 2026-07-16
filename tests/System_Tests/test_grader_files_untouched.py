"""HARD requirement (HW3.pdf p.1): id_123456789_987654321.py is "the ONLY file in the exercise
you may change". The grader-provided files -- server.py, CONSTANTS.py, and the three naive
dummies -- must stay byte-for-byte as downloaded from Moodle (we build/verify against them but
never modify them). This test pins their sha256 so ANY edit to a fixture fails CI, and doubles as
a re-published-grader tripwire (if the staff swaps server.py, the mismatch tells us to re-verify).

Hashes verified 2026-07-10 to MATCH the original HW3.zip from Moodle.
STAFF RE-PUBLISHED server.py + CONSTANTS.py on 2026-07-16 (announcement "הבהרות ועדכונים - תרגיל בית 3"):
added the ENFORCE_TIME_CAP fast-mode flag, PASS_TOLERANCE (95% relief), NUM_SIMULATIONS=10000, and a
print_threshold_check. Diff-verified: the SIMULATION LOGIC is unchanged (only the enforcement path +
reporting differ), so all prior results still hold. server.py + CONSTANTS.py re-pinned below; the
three dummies and the template are byte-identical to the original (unchanged, re-confirmed).
"""
import hashlib
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# sha256 of the untouched grader files (server.py + CONSTANTS.py = the 2026-07-16 re-publish).
OG_SHA256 = {
    "server.py": "b8ee1b051a2fbc5135391f5672b0f0806c8a04efb0b519806a807c745b63e11e",
    "CONSTANTS.py": "d04958becde600a8543db1ced96a1c903b03250766734759db74b184e8770614",
    "id_dummy_1.py": "c7ce946ea1a50362a73a863114f8c51876a9869a7b5faa9332385e01aa443626",
    "id_dummy_2.py": "868c334c3678416d9c18b9193aca5828c8357383d00e193b36934a58ad80f3a7",
    "id_dummy_3.py": "80edbb7b5a3a39d1cf6d248bef1d9566bffea5856c664f0b983b44247c928c87",
    "id_123456789_987654321.py": "00a96984bcd8376dd1ea7c46ca19fef7eac38a060aeb916e6883890af4e11422",
}


@pytest.mark.parametrize("name,expected", sorted(OG_SHA256.items()))
def test_grader_file_is_unmodified(name, expected):
    actual = hashlib.sha256((FIXTURES / name).read_bytes()).hexdigest()
    assert actual == expected, (
        f"{name} differs from the Moodle original -- we must NOT modify grader files "
        f"(only the agent file). If the staff RE-PUBLISHED the grader, re-verify against the new "
        f"HW3.zip and update the pinned hash."
    )
