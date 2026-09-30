# Handoff - location and count fixes validated, 2026-09-30

FINISHED locally: issue #19 reproduced and fixed through assembly-aware
preprocessing. 294 captured NASM comparisons pass. PRO PR21-23 are integrated
into this branch with their original commit history; 20 combined focused
methods and the 244-method native suite pass (one optional corpus skip).
The complete DOSCTRL worker matches native NASM, including its historical
3,091-byte hash. Evidence: doc/PREPROCESSOR_LOCATION.md and linked receipt.

WIP: PR24 awaits final Windows/Linux CI on this documentation head, then
merge and remove integrated feature/transfer branches. Parent pin upgrade
and full parent parity/static validation remain WIP. Do not claim new Pascal
translation or gameplay evidence from these assembler-only checks.

Earlier PR16-18 were integrated through PR20. Use one bounded game-owned
ASM-to-Pascal routine for the next PRO run after parent synchronization.
