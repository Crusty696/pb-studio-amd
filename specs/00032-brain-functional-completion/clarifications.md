# Clarifications: Brain/HIRN Functional Completion

- The user ordered fixes first and prohibited all tests until explicit authorization.
- “Brain/HIRN” includes `src/pb_studio/brain/**`, Brain backend routes/schemas, productive pacing integration boundaries, and the HIRN WPF view/view-model/API contracts.
- Existing accepted architecture decisions remain binding; this task repairs implementation defects rather than redesigning the learning algorithm.
- Existing user learning data must remain untouched. Reset or migration is not authorized.
- Source-complete does not mean runtime-complete. Test/QC tasks remain open after implementation.
