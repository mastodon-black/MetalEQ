# Creates MetalEQ shortcuts on the Desktop and in the Start menu.
# Called by install.bat; safe to re-run (existing MetalEQ shortcuts are replaced).
$ErrorActionPreference = 'Stop'

$root   = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Join-Path $root 'run.bat'
$icon   = Join-Path $root 'equalizer\icons\audio-equalizer.ico'

$shell = New-Object -ComObject WScript.Shell

# GetFolderPath follows redirected folders (e.g. OneDrive Desktop).
$folders = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('Programs')   # per-user Start menu > Programs
)

foreach ($folder in $folders) {
    if (-not $folder -or -not (Test-Path -LiteralPath $folder)) { continue }
    $path = Join-Path $folder 'MetalEQ.lnk'
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath       = $target
    $lnk.WorkingDirectory = $root
    $lnk.IconLocation     = $icon
    $lnk.Description      = 'MetalEQ - free system-wide audio equalizer, designed for metal'
    $lnk.WindowStyle      = 7   # minimized: run.bat's console window stays out of the way
    $lnk.Save()
    Write-Host "  created: $path"
}
