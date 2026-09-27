# Clarifications: PB Studio Full Audit Remediation

## Resolved Scope and Decisions

- One new master workspace `00035-full-audit-remediation`; existing Specs 00029–00034 remain historical and unchanged.
- All 54 numbered findings are traced. Duplicate evidence points share a fix/test; conditional risks need positive and negative-path proof. Finding 54 is withdrawn and gets no product change.
- User authorized implementing the complete plan, regression/full-suite tests, builds, and API/live checks. Controlled WPF GUI operation waits until user hands over PB Studio.
- Reuse one existing QA project and approved media. Do not create repeated QA projects or delete user media/projects/old test artifacts.
- Keep existing dirty files; no commit, push, merge, install, dependency/version change, or schema/FAISS migration.
- Maintain DirectML/AMF, Python/NumPy, Windows path, and `Tests/` constraints; `separator.py` remains locked.
- Music timing/relevance is primary; narrative theme continuity is bounded and secondary; diversity breaks ties.
- The Brain `INDEX.md` and `_wiki/decisions` paths specified by AGENTS.md were absent at inspection. Existing repository ADRs 0001–0004 are the available architecture decision source.
