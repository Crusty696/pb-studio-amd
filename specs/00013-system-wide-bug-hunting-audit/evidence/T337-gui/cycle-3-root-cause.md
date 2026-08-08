# T337 GUI Cycle 3 Root Cause

- Status: `CONFIRMED`
- Runtime window: 2576 × 1408 pixels
- `channel_range_sum`: 405
- `unique_sample_colors`: 14
- UIA/runtime state: Release window visible and responsive
- Screenshot: `screenshots-cycle-3/projekt.png`

The screenshot contains the complete PB Studio project surface, navigation,
project controls, status cards, and online backend indicator. The product did
not render a blank surface.

The failed gate combined the documented color-variance condition with an
unsupported `unique_sample_colors > 20` condition. PB Studio's flat-color WPF
theme legitimately uses fewer than 21 sampled colors across a mostly empty
project workspace. Cycle 4 keeps the documented `channel_range_sum > 30`
blank-surface gate and the independent UIA visible-control gate.
