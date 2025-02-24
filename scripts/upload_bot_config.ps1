try {
    Write-Warning "This script will replace the bot config on the server."
    Pause
    Import-Module Set-PsEnv
    
    Set-PsEnv
    
    $scriptDirPath = Split-Path -Parent $MyInvocation.MyCommand.Path
    $botDirPath = Split-Path -Parent $scriptDirPath
    $botConfigPath = "$botDirPath\data\bot_configuration_production.json"
    
    Write-Host "Server URL: $Env:SERVER_URL"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/set_bot_config" `
        -Method 'Post' `
        -Headers @{'token' = $Env:SERVER_TOKEN; "Content-Type"="application/json"} `
        -Body (Get-Content -Raw -Path $botConfigPath)
}
catch {
    Write-Host $_
    Pause
}