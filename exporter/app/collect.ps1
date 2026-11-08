$ErrorActionPrefrence = 'STOP'
$services = '__SERVICES__' -split ',' | Where-Object { $_ }

try {
$cpu = (Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'").PercentProcessorTime
} catch {    
$cpu = (Get-CimInstance Win32_Processor | Measure-Object -Property LoadPercentage -Average).Average
}
$os = Get-CimInstance Win32_OperatingSystem
$disks = @(Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | ForEach-Object {    
[pscustomobject]@{ volume = $_.DeviceID; size = [double]$_.Size; free = [double]$_.FreeSpace }
})
$svc = @(foreach ($name in $services) {    
$s = Get-Service -Name $name -ErrorAction SilentlyContinue
[pscustomobject]@{ name = $name; exists = [bool]$s; running = [bool]($s -and $s.Status -eq 'Running') }
})
[pscustomobject]@{    
computername = $env:COMPUTERNAME
cpu          = [double]$cpu    
mem_total    = [double]$os.TotalVisibleMemorySize * 1024    
mem_free     = [double]$os.FreePhysicalMemory * 1024    
uptime       = [double]((Get-Date) - $os.LastBootUpTime).TotalSeconds    
disks        = $disks    
services     = $svc
} | ConvertTo-Json -Compress -Depth 4
