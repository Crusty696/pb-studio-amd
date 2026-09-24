# Clarifications: Video/Vision Functional Completion

- The user ordered fixes first and prohibited all tests until explicit authorization.
- “Video/Vision” includes `src/pb_studio/video/**`, video backend routes/schemas, productive state/persistence boundaries, and Video Library WPF/API contracts.
- RAFT, SigLIP, and the vision LLM are separate specialized stages; one vision model does not replace motion or embedding analysis.
- The model-centric multi-clip order and provider/model pinning from Spec 00031 remain binding.
- Missing DirectML assets disable only their capability and must not activate CPU neural fallback.
- Source-complete does not mean runtime-complete. Test/QC tasks remain open after implementation.
