# Administrator PowerShell. Allow only peer cluster traffic and explicit client subnet.
param(
    [Parameter(Mandatory=$true)][string]$PeerIP,
    [Parameter(Mandatory=$true)][string]$ClientSubnet
)
$ErrorActionPreference = 'Stop'
$taskPeer = [System.Net.IPAddress]::Parse($PeerIP)
if ($taskPeer.AddressFamily -ne [System.Net.Sockets.AddressFamily]::InterNetwork) { throw 'PeerIP harus IPv4.' }
if (-not (Get-Command New-NetFirewallHyperVRule -ErrorAction SilentlyContinue)) {
    throw 'Hyper-V firewall cmdlet tidak tersedia. Periksa Windows 11 22H2+ dan WSL terbaru.'
}
$taskCreator = '{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}'
$taskRules = @(
    @{Name='SokaClusterTCP'; Protocol='TCP'; Ports=@(6443,10250,18080); Remote=$PeerIP},
    @{Name='SokaClusterUDP'; Protocol='UDP'; Ports=@(8472); Remote=$PeerIP},
    @{Name='SokaResults'; Protocol='TCP'; Ports=@(30080); Remote=$ClientSubnet}
)
foreach ($taskRule in $taskRules) {
    Get-NetFirewallRule -Name $taskRule.Name -ErrorAction SilentlyContinue | Remove-NetFirewallRule
    New-NetFirewallRule -Name $taskRule.Name -DisplayName $taskRule.Name -Direction Inbound -Action Allow -Protocol $taskRule.Protocol -LocalPort $taskRule.Ports -RemoteAddress $taskRule.Remote | Out-Null
    Get-NetFirewallHyperVRule -Name $taskRule.Name -ErrorAction SilentlyContinue | Remove-NetFirewallHyperVRule
    New-NetFirewallHyperVRule -Name $taskRule.Name -DisplayName $taskRule.Name -Direction Inbound -Action Allow -VMCreatorId $taskCreator -Protocol $taskRule.Protocol -LocalPorts $taskRule.Ports -RemoteAddresses $taskRule.Remote | Out-Null
}
Write-Host 'Aturan lab dibuat. Firewall tetap aktif; trafik cluster dibatasi ke IP peer.'
