try {
    Import-Module Set-PsEnv
    
    Set-PsEnv
    
    Write-Host "Server URL: $Env:SERVER_URL"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/get_slot_machine_config" `
        -Method 'Get' `
        -Headers @{'token' = $Env:SERVER_TOKEN} `
        -OutFile "slot_machine_downloaded.json"
}
catch {
    Write-Host "Failed to download slot machine configuration."
    Write-Host $_
    Pause
}