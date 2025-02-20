try {
    Import-Module Set-PsEnv
    
    Set-PsEnv
    
    Write-Host "Server URL: $Env:SERVER_URL"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/download_save_data" `
        -Method 'Get' `
        -Headers @{'token' = $Env:SERVER_TOKEN} `
        -OutFile "save_data.zip"
}
catch {
    Write-Host "Failed to download save data."
    Write-Host $_
    Pause
}