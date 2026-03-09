---
name: Research & Documentation
description: Guidelines for conducting deep technical research, maintaining documentation, and analyzing complex problems in the PB Studio context.
---

# Research & Documentation Skill

## Core Principles
- **Living Documents:** Documentation is not an afterthought. It is the map for the code.
- **Deep Analysis:** Don't just copy-paste solutions. Understand *why* they work, especially for AMD/DirectML edge cases.

## 1. Research Protocol
When faced with a new problem or unknown technology:
1. **Define the Question:** What exactly are we solving? (e.g., "How to get Moondream running on DirectML with FP16").
2. **Search Efficiently:** Use `search_web` with specific keywords (`onnxruntime directml fp16 issues`).
3. **Verify Findings:** Don't trust the first StackOverflow answer. Cross-reference with official docs (Microsoft, ONNX).
4. **Synthesize:** Summarize findings in a markdown note or directly in the `implementation_plan.md`.

## 2. Documentation Standards
- **Language:** German (as per user preference) or English (technical standard) - *User specified German for communication, so docs should be compatible.*
- **Format:** Markdown.
- **Location:** Update `README.md` for user-facing changes, and `MASTER_PLAN_v10.md` or `TODO.md` for internal tracking.

## 3. The "Interaction Log"
- Keep `interaction_log.md` (if it exists) or `task.md` updated with major decisions.
- Record "Lessons Learned" to avoid repeating mistakes (e.g., "DirectML requires specific opset version 14").
