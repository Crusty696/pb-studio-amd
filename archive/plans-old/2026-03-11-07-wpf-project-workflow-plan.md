# Work Plan – WPF Project Workflow

Date: 2026-03-11
Status: completed

## Goal
Close the highest-leverage product gap by making project lifecycle actions available in the real WPF shell.

## Scope
- expose `/project/create|open|save|close|info` through `IApiClient`/`ApiClient`
- replace stubbed `ProjectService` logic with real backend-backed behavior
- add project state + commands to `MainViewModel`
- expose minimal project actions in `MainWindow.xaml`
- verify clean WPF build

## Result
- completed
