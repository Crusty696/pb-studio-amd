Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$screen = [System.Windows.Forms.Screen]::PrimaryScreen
$bounds = $screen.Bounds
$bitmap = New-Object System.Drawing.Bitmap($bounds.Width, $bounds.Height)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.Size)

$outputPath = "C:\Users\david\Documents\Pb_studio_AMD_version\gui_screenshots\desktop_snapshot.png"
if (-not (Test-Path "C:\Users\david\Documents\Pb_studio_AMD_version\gui_screenshots")) {
    New-Item -ItemType Directory -Path "C:\Users\david\Documents\Pb_studio_AMD_version\gui_screenshots" -Force | Out-Null
}
$bitmap.Save($outputPath, [System.Drawing.Imaging.ImageFormat]::Png)

$graphics.Dispose()
$bitmap.Dispose()
Write-Output "Screenshot erfolgreich unter $outputPath gespeichert."
