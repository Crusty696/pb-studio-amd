# Product Requirements Document: PB Studio (AMD-Version)

> Date: 2026-04-24 | Status: Draft

## Product Overview
PB Studio is a specialized local AI multimedia workstation designed for complex media processing and AI-assisted analysis. It operates completely offline and provides full support for AMD hardware via DirectML. Its primary value is the autonomous creation of professional visual accompaniment for long DJ mixes, acting as an "AI Director".

## Vision and Why Now
The vision is to empower creators to produce high-quality, rhythmically perfect music videos and visual sets without the hundreds of hours typically required for manual editing. With the rise of powerful local AI and the increasing accessibility of high-performance AMD hardware, now is the time to bring professional-grade automation to the local desktop.

## Problem Statement
Creating visual accompaniment for DJ mixes (often 1-4 hours long) is an immense manual effort. Syncing every cut to the beat, matching the energy of the music, and selecting appropriate footage from thousands of clips is cognitively exhausting and time-prohibitive for most creators.

## Background and Evidence
Domain context shows a clear gap between "simple visualizers" (low quality) and "manual editing" (high effort). Users in the DJ and VJ community frequently seek ways to automate the "donkey work" of cutting clips while retaining creative control over the final narrative.

## Target Users, Stakeholders, and Core Personas

### Target Users
- **DJs & Music Producers**: Want to promote their mixes with high-quality visuals.
- **VJs (Visual Jockey)**: Need automated tools to assist in live set preparation or content generation.
- **Content Creators**: Social media influencers needing rapid, beat-synced content.

### Stakeholders
- **Lead Developer**: Ensures technical feasibility and performance on AMD hardware.
- **End Users**: Provide feedback on the quality and "feel" of the AI cuts.

### Core Personas
- **DJ David** — Busy performer who wants to upload his 2-hour set to YouTube with visuals that look like they were edited by a pro, but only has 30 minutes to set it up.

## User Needs / Jobs To Be Done
- **Automatic Syncing**: I need my video cuts to land perfectly on the beats of my music.
- **Footage Orchestration**: I need a system that selects the "right" footage based on the mood and energy of the audio.
- **Local Control**: I need to do all of this without uploading gigabytes of footage to a cloud service.
- **Interactive Fine-Tuning**: I need to be able to manually adjust AI-suggested cuts on a timeline.

## Product Principles or UX Principles
- **Hardware Inclusivity**: Must run flawlessly on AMD GPUs via DirectML.
- **Privacy First**: Zero cloud dependencies; all analysis stays on the local machine.
- **Rhythmic Perfection**: A cut that misses the beat is a failure.
- **Performance**: High-intensity AI tasks must not freeze the UI.

## Scope Summary
The initial release focuses on the core "AI Director" loop: audio analysis, video library indexing, automated pacing generation, and final video rendering.

### In-Scope Capabilities
- **Audio Analysis**: BPM detection, beat tracking, mood/energy classification.
- **Video Library**: local indexing of thousands of clips with AI-based content tagging.
- **Pacing Engine**: logic to assemble a timeline based on audio triggers.
- **Interactive Timeline**: Visual track-based editor for reviewing and adjusting cuts.
- **Rendering**: Hardware-accelerated export (AMD AMF).

### Out-of-Scope Items
- **Live VJing**: Real-time output to a projector is deferred.
- **Cloud Collaboration**: Multi-user editing is out of scope.
- **Advanced VFX**: Plugins and complex transitions are deferred to future versions.

## Product Capability Map

| Capability ID | Capability | Priority | Outcome |
|---------------|------------|----------|---------|
| CAP-001 | AI Audio Director | P1 | Automated beat and energy analysis of long audio files. |
| CAP-002 | Smart Video Library | P1 | AI-tagged local video database with content search. |
| CAP-003 | Auto-Pacing Engine | P1 | Rule-based generation of a complete video timeline. |
| CAP-004 | Power-Timeline | P1 | Interactive editor for manual adjustment of AI cuts. |
| CAP-005 | AMD Export Pipeline | P1 | High-speed video rendering using AMD AMF. |

## Success Metrics / KPIs / Desired Outcomes

| Metric | Target | Why It Matters | Measurement Window |
|--------|--------|----------------|--------------------|
| Cut Accuracy | > 98% | Misaligned cuts break the "magic". | Per project |
| Analysis Speed | < 0.5x Real-time | 1h mix should be analyzed in < 30m. | Per run |
| UI Responsiveness | Zero Freezes | Large timelines must remain fluid. | Always |

## Assumptions
- Users have an AMD or Intel GPU supporting DirectML for optimal performance.
- Users provide their own high-quality video footage library.

## Constraints
- **Technical**: Must use Python for AI logic and C# for the UI.
- **Operational**: Must run on Windows 10/11.

## Dependencies
- **FFmpeg**: Required for all media transcoding and rendering.
- **DirectML**: Required for hardware-accelerated AI inference.

## Risks
- **Model Size**: Local AI models may require significant disk space and VRAM.
- **Complexity**: Synchronizing thousands of clips on a timeline is performance-intensive.

## Open Questions
- Should we support VST plugins for audio reactive effects in the first release? (Current answer: Deferred).

## Release or Validation Approach
Internal alpha testing with professional DJ mixes, followed by a framework-dependent beta release for community feedback.

## Domain Glossary / Terminology
- **Pacing**: The rhythm and timing of video cuts relative to music.
- **Trigger**: An audio event (beat, onset, energy spike) that signals a potential cut.
- **EDL**: Edit Decision List – the data structure representing the timeline.

## Handoff Guidance

- **Product intent to preserve**: The focus on "Rhythmic Perfection" must drive all architecture decisions.
- **Scope boundaries to respect**: Local-only processing is a non-negotiable constraint.
- **Critical constraints**: Hardware acceleration must prioritize AMD via DirectML.

## Project Context Baseline Updates
- [None yet]
