param(
    [ValidateSet('setup', 'plan', 'verify', 'run')]
    [string]$Mode = 'run',
    [ValidateRange(100, 1000)]
    [int]$DatasetSize = 100,
    [int]$Tasks = 0,
    [switch]$AllDatasets,
    [ValidateSet('k3s', 'kind')]
    [string]$ClusterMode = 'k3s'
)
$ErrorActionPreference = 'Stop'
if ($Tasks -lt 0) { throw 'Tasks harus positif, atau 0 untuk seluruh dataset.' }
if ($DatasetSize % 50 -ne 0) { throw 'DatasetSize harus kelipatan 50 dari 100 sampai 1000.' }
if ($AllDatasets -and ($Mode -notin @('run', 'plan') -or $Tasks -ne 0)) {
    throw 'AllDatasets hanya untuk run/plan seluruh dataset, tanpa Tasks.'
}
if ($ClusterMode -eq 'k3s') {
    $taskK3sArgs = @('env', 'SOKA_CLUSTER_MODE=k3s', 'SOKA_KUBE_CONTEXT=default', 'KUBECONFIG=.kube/k3s.yaml', 'python3')
    if ($Mode -eq 'setup') {
        $taskK3sArgs += @('kube_backend.py', 'setup')
    } elseif ($Mode -eq 'run') {
        $taskK3sArgs += @('scripts/submit_experiment.py', '--dataset-size', "$DatasetSize")
        if ($AllDatasets) { $taskK3sArgs += '--all-datasets' }
        if ($Tasks -gt 0) { $taskK3sArgs += @('--tasks', "$Tasks") }
    } else {
        if ($AllDatasets) { throw 'Gunakan Ubuntu untuk plan banyak dataset; AllDatasets dari PowerShell hanya untuk run.' }
        $taskK3sArgs += @('scheduler.py', $Mode, '--dataset-size', "$DatasetSize")
        if ($Tasks -gt 0) { $taskK3sArgs += @('--tasks', "$Tasks") }
    }
    & wsl -d Ubuntu --cd $PSScriptRoot -- @taskK3sArgs
    if ($LASTEXITCODE -ne 0) { throw 'Perintah K3s gagal. Periksa node, kubeconfig dan panduan docs/K3S-DUA-LAPTOP.md.' }
    exit 0
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
