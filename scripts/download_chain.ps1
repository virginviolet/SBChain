try {
    Import-Module Set-PsEnv
    
    Set-PsEnv
    
    Write-Host "Server URL: $Env:SERVER_URL"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/download_chain" `
        -Method 'Get' `
        -OutFile "blockchain_downloaded.json"
}
catch {
    Write-Host "Failed to download blockchain."
    Write-Host $_
    Pause
}