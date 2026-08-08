# T337 Cycle 6 Model Capture Limitation

- Post-fix EXPORT rendering and WPF-log gates: `PASS`
- EXPORT screenshot: valid, eight SSE log entries visible
- MODELLE screenshot timing: captured before refresh completed

Cycle 6 proves the XAML fix but is not used for final Models UI/API parity.
Cycle 7 waits for the exact installed-count prefix returned by the live
`/models/list` endpoint before capturing the Models tab.
