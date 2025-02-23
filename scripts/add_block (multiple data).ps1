param(
    [array]$data
)
try {
    Import-Module Set-PsEnv
    
    Set-PsEnv
    
    Write-Host "Server URL: $Env:SERVER_URL"
    $body = @{"data" = $data} | ConvertTo-Json
    Write-Host "Body: $body"
    Invoke-RestMethod -Uri "$Env:SERVER_URL/add_block" `
        -Method 'Post' `
        -Headers @{'token' = $Env:SERVER_TOKEN} `
        -ContentType 'application/json' `
        -Body $body
}
catch {
    Write-Host "Failed to add block."
    Write-Host $_
    Pause
}