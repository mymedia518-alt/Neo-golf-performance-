# Fetch Blue Heron East Hole 8's two official course-guide images.
#
# Tournament H8 = Blue Heron East Hole 8 (confirmed: NEO_COURSE_IDENTITY_VERIFICATION.md,
# 18-hole systematic yardage cross-check, Blue tee 377yd = Tournament 377yd exact match).
#
# URL template confirmed real (not guessed) from real network traffic captured during
# the West Hole 3 fetch (see neo_klpga_shot_source/fetch_blueheron_hole_images.py).
# This script only substitutes side=east, hole=08 into that already-verified template.
#
# Run from anywhere; it saves relative to this script's own location, so the repo
# layout stays correct regardless of your current directory.
#
# Usage (PowerShell):
#   .\fetch_h8_official_assets.ps1

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = Join-Path $repoRoot "course_maps\blue_heron\east\hole_08"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$targets = @{
    "visual" = "https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-visual-east-hole08.png"
    "tip"    = "https://blueheron.co.kr/static/pc/origin/assets/images/page/course-information-hole-information-tip-east-hole08.png"
}

$headers = @{
    "User-Agent" = "Mozilla/5.0 NEO-Golf-Data/1.0"
    "Referer"    = "https://www.blueheron.co.kr/"
}

$okCount = 0
foreach ($kind in $targets.Keys) {
    $url = $targets[$kind]
    $outPath = Join-Path $outDir "$kind.png"
    try {
        Invoke-WebRequest -Uri $url -Headers $headers -OutFile $outPath -UseBasicParsing
        $size = (Get-Item $outPath).Length
        Write-Host "OK   $kind : $size bytes -> $outPath"
        $okCount++
    } catch {
        Write-Host "FAIL $kind : $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "$okCount/2 fetched."
if ($okCount -eq 2) {
    Write-Host "Next: python verify_h8_official_assets.py"
}
