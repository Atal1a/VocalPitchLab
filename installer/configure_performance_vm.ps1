[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Mandatory=$true)][string]$VMName,
    [ValidateSet('8gb','4gb')][string]$Profile = '8gb',
    [ValidateRange(1,100)][int]$CpuMaximum = 100
)

$ErrorActionPreference = 'Stop'
Import-Module Hyper-V -ErrorAction Stop
$matches = @(Get-VM -Name $VMName | Where-Object { $_.Name -ceq $VMName })
if ($matches.Count -ne 1) { throw 'Choose the exact name of one existing test VM.' }
$testVM = $matches[0]
if ($testVM.State -ne 'Off') { throw 'Shut down the test VM before applying a fixed-memory profile.' }
$testCpus = if ($Profile -eq '8gb') { 4 } else { 2 }
$testMemory = if ($Profile -eq '8gb') { 8GB } else { 4GB }
if ($PSCmdlet.ShouldProcess($testVM.Name, "Set $testCpus virtual processors, $Profile fixed memory, and $CpuMaximum percent CPU maximum")) {
    Set-VMProcessor -VM $testVM -Count $testCpus -Maximum $CpuMaximum
    Set-VMMemory -VM $testVM -DynamicMemoryEnabled $false -StartupBytes $testMemory
    Get-VM -Id $testVM.Id | Select-Object Name, State, ProcessorCount, MemoryStartup, DynamicMemoryEnabled
    Get-VMProcessor -VM $testVM | Select-Object Count, Maximum
}
