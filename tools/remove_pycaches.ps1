<#
.SYNOPSIS
  Remove all __pycache__ directories under a root (Windows PowerShell).

USAGE
  # Dry-run (list only)
  .\tools\remove_pycaches.ps1 -Root . 

  # Delete for real
  .\tools\remove_pycaches.ps1 -Root . -Delete

  # Recursive, force delete
  .\tools\remove_pycaches.ps1 -Root C:\path\to\project -Delete
#>

param(
    [string]$Root = ".",
    [switch]$Delete
)

try {
    $rootPath = Resolve-Path -Path $Root -ErrorAction Stop
} catch {
    Write-Error "Root path not found: $Root"
    exit 2
}

Write-Host "Scanning for __pycache__ under: $rootPath"

$found = Get-ChildItem -Path $rootPath -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue

if (-not $found) {
    Write-Host "No __pycache__ directories found."
    exit 0
}

if (-not $Delete) {
    Write-Host "Dry-run: the following __pycache__ directories would be removed:"
    $found | ForEach-Object { Write-Host "- $($_.FullName)" }
    Write-Host "`nRerun with -Delete to remove them."
    exit 0
}

# Delete
foreach ($d in $found) {
    try {
        Remove-Item -LiteralPath $d.FullName -Recurse -Force -ErrorAction Stop
        Write-Host "Removed: $($d.FullName)"
    } catch {
        Write-Warning "Failed to remove $($d.FullName): $_"
    }
}
Write-Host "Done."