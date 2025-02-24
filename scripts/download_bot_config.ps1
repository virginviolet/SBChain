try {
    Import-Module Set-PsEnv

    Set-PsEnv

    Write-Host "Server URL: $Env:SERVER_URL"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/get_bot_config" `
        -Method 'Get' `
        -Headers @{'token' = $Env:SERVER_TOKEN } `
        -OutFile "bot_configuration_downloaded.json"
} catch {
    Write-Host "Failed to download bot config."
    Write-Host $_
    Pause
}