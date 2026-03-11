# Work Plan – WPF Startup Smoke / Crash Fix

Date: 2026-03-11
Status: completed

## Goal
Run the real WPF app startup path and fix startup blockers immediately instead of relying only on compile success.

## Trigger
`dotnet run --project PBStudio.UI/PBStudio.UI.csproj -c Debug` crashed during window startup.

## Initial finding
- `TimelineView.xaml` bound read-only computed properties without `Mode=OneWay`
- WPF attempted TwoWay binding and crashed on startup

## Success criteria
- clean build
- real app startup reaches running state without immediate exception
