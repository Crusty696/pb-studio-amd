<!-- template-version: 2 -->
# PB Studio (AMD-Version) Project Instructions

## Core Principles

### I. AMD DirectML First
The application MUST support AMD hardware via DirectML (`onnxruntime-directml`). CUDA-only paths are strictly prohibited to ensure hardware inclusivity for AMD and Intel users.

### II. Offline First
All AI models and media processing MUST run locally on the user's machine. Cloud dependencies for core functionality are prohibited to protect user privacy and ensure operational reliability without internet.

### III. Quality Over Speed
AI analysis and video generation SHOULD prioritize high-quality, rhythmically perfect results over processing speed. The "AI Director" must ensure beats and visual cuts are perfectly synchronized.

### IV. Agent Output Style
All agent output MUST be concise and outcome-oriented. This principle supersedes any verbose defaults.

### V. Obsidian Brain First
The Obsidian Vault at `C:\Users\david\Brain` is the system's Long-Term Memory.
- **Consult before action**: Every agent MUST check the Brain (`_wiki/decisions`, `INDEX.md`) before proposing architectural changes.
- **Update after success**: Every successful milestone MUST be documented in the Brain's project log and wiki.
- **Cross-Agent Knowledge**: Learnings discovered by one agent must be written to the Brain to ensure continuity across all future sessions and sub-agents.

- **Progress reports**: Facts and outcomes only — no narration, no restating the task.
- **Artifacts**: Emit required sections only — no preamble paragraphs, no summary epilogues.
- **Reasoning**: Omit unless the user asks "why" or the decision is non-obvious.
- **Errors / blockers**: State the problem, the attempted fix, and the result — nothing else.
- **Phase-boundary reports**: ≤ 5 bullet points.
- **Preserve without compressing**: Artifact template structure and required sections; explicit decision / registration / validation guidance in shared skills; delegation constraints and sub-agent role definitions; existing size limits (spec ≤ 10 KB, research ≤ 4 KB, stories ≤ 200 words).

## Technology Stack

- **Language/Runtime**: Python 3.11 / .NET 9 (C#)
- **Frameworks**: FastAPI (Backend), WPF (Frontend)
- **Storage**: FAISS (Vector Store), JSON (Project State)
- **Infrastructure**: local only (AMD DirectML)

## Testing & Quality Policy

- **Coverage Target**: none
- **Required QC Categories**: linting
- **Test Strategy**: Unit + integration (pytest for Python, dotnet test for C#); E2E verification via pywinauto.
- **Linting / Formatting**: Ruff (Python), Roslyn Analyzers (C#)

## Source Code Layout

- **Policy**: PRESERVE_EXISTING_LAYOUT
- **Convention**: Python logic in `/src/pb_studio`, FastAPI in `/backend`, WPF in `/PBStudio.UI`, tests in `/Tests`.

## Development Workflow

- **Branching**: Feature branches from main, squash merge
- **Commit Convention**: Conventional Commits
- **CI Requirements**: All tests pass, build clean before merge

## Governance

- Project instructions supersede all other documentation and practices.
- Amendments require a version bump with ISO-dated changelog entry.
- All implementations MUST pass the Instructions Check gate during planning.
- Complexity beyond these principles MUST be justified and documented.

**Version**: 1.0.0 | **Last Amended**: 2026-04-24
