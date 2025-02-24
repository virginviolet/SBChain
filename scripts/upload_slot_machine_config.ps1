try {
    Write-Warning "This script will replace the slot machine configuration on the server."
    Pause
    Import-Module Set-PsEnv
    
    Set-PsEnv
    
    $scriptDirPath = Split-Path -Parent $MyInvocation.MyCommand.Path
    $botDirPath = Split-Path -Parent $scriptDirPath
    $slotMachineConfigPath = "$botDirPath\data\slot_machine_production.json"
    
    Write-Host "Server URL: $Env:SERVER_URL"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/set_slot_machine_config" `
        -Method 'Post' `
        -Headers @{'token' = $Env:SERVER_TOKEN; "Content-Type"="application/json"} `
        -Body (Get-Content -Raw -Path $slotMachineConfigPath)
}
catch {
    Write-Host $_
    Pause
}