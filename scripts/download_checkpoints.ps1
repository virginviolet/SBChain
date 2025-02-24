try {
    Import-Module Set-PsEnv
    
    Set-PsEnv
    
    Write-Host "Server URL: $Env:SERVER_URL"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/download_checkpoints" `
        -Method 'Get' `
        -Headers @{'token' = $Env:SERVER_TOKEN} `
        -OutFile "checkpoints_downloaded.zip"
}
catch {
    Write-Host "Failed to download checkpoints."
    Write-Host $_
    Pause
}