# T337 Cycle 5 Screenshot Limitation

- Functional UIA and WPF-log gates: `PASS`
- `PrintWindow(PW_RENDERFULLCONTENT)` screenshot quality: `FAIL`
- Product rendering conclusion from Cycle 5 images: none

The hardware-accelerated WPF surface returned white and black regions through
`PrintWindow`. Cycle 5 images are retained as failure evidence but are not used
as visual proof. Cycle 4 already contains valid full-window screenshots. Cycle
6 repeats the post-fix focused capture with WPF and pywinauto on the same tool
desktop.
