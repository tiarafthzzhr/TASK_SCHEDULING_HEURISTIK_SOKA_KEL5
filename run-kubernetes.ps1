param(
    [ValidateSet('setup', 'plan', 'verify', 'run')]
    [string]$Mode = 'run',
    [ValidateRange(100, 1000)]
    [int]$DatasetSize = 100,
    [int]$Tasks = 0,
    [switch]$AllDatasets
)
$ErrorActionPreference = 'Stop'
if ($Tasks -lt 0) { throw 'Tasks harus positif, atau 0 untuk seluruh dataset.' }
if ($DatasetSize % 50 -ne 0) { throw 'DatasetSize harus kelipatan 50 dari 100 sampai 1000.' }
if ($AllDatasets -and ($Mode -notin @('run', 'plan') -or $Tasks -ne 0)) {
    throw 'AllDatasets hanya untuk run/plan seluruh dataset, tanpa Tasks.'
}
if ($Mode -eq 'setup') {
    & wsl -d Ubuntu --cd $PSScriptRoot -- python3 kubernetes/install_kind.py
    if ($LASTEXITCODE -ne 0) { throw 'Pemasangan kind gagal.' }
    & wsl -d Ubuntu --cd $PSScriptRoot -- python3 kube_backend.py setup
} else {
    $taskDatasetSizes = if ($AllDatasets) { 100..1000 | Where-Object { $_ % 50 -eq 0 } } else { @($DatasetSize) }
    foreach ($taskSize in $taskDatasetSizes) {
        $taskArguments = @('scheduler.py', $Mode, '--dataset-size', "$taskSize")
        if ($Tasks -gt 0) { $taskArguments += @('--tasks', "$Tasks") }
        Write-Host "`nDataset GoCJ: $taskSize task" -ForegroundColor Cyan
        & wsl -d Ubuntu --cd $PSScriptRoot -- python3 @taskArguments
        if ($LASTEXITCODE -ne 0) { throw "Eksekusi dataset $taskSize gagal; rangkaian dihentikan." }
    }
}
if ($LASTEXITCODE -ne 0) { throw 'Perintah gagal. Periksa pesan error dan pastikan Docker Desktop aktif.' }
