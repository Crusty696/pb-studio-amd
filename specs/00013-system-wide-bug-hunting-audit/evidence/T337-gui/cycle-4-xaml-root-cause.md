# T337 Cycle 4 XAML Runtime Root Cause

- Status: `CONFIRMED`
- First failure: 2026-07-29 14:01:31.296 +02:00
- Source log bytes: 28,241,063,490
- Source log SHA-256:
  `D36CF76F9B6CC313F57839EC00EA25AA3BB8781BD0A13F33D661EFA49F8E232B`
- Unhandled UI exceptions: 30,227
- Direct `XamlParseException` records: 30,227
- Unobserved aggregate exception records: 3,350,405
- Full archive: `wpf-cycle-4-exception-storm.tar.zst`
- Archive bytes: 14,384,477
- Archive SHA-256:
  `B58BE603AD1F428FF9AF1344931BAC0D062FF65FAB3928AA123158DD87D8E627`
- Archive listing verification: `tar.exe --zstd -tf` exit 0,
  member `logs/wpf_app.log`

## Root Cause

`ProductionViewModel.RenderLogEntries` is an
`ObservableCollection<string>`. Its copyable log template used a read-only
`TextBox` with `Text="{Binding}"`. `TextBox.Text` binds TwoWay by default.
WPF therefore rejected the pathless binding while materializing log items:

`SSE LogReceived -> RenderLogEntries -> ListBox DataTemplate ->
TextBox.Text TwoWay/pathless -> XamlParseException`.

The application exception logger then fed the exception to
`TerminalLoggerProvider`. `TerminalViewModel` updated its terminal TextBox,
which forced another layout pass and retriggered the same invalid template.
That produced the observed exception/log amplification.

## Fix Contract

The template remains selectable and read-only. Its string item binding is now
explicitly `Text="{Binding Path=., Mode=OneWay}"`. No ViewModel, API, DTO,
backend, model-registry, or data contract changed.

## Static Verification

- `ProductionView.xaml` XML parse: PASS
- Pathless `TextBox.Text="{Binding}"` search: no matches
- WPF Release build: PASS, 0 warnings, 0 errors
