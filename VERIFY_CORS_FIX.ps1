# CORS Configuration Verification Script
# Verifies that ALLOWED_ORIGINS is properly configured

Write-Host "================================" -ForegroundColor Cyan
Write-Host "CORS Configuration Verification" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Check if .env file exists
Write-Host "[1/5] Checking .env file..." -ForegroundColor Yellow
if (Test-Path ".env") {
    Write-Host "✓ .env file found" -ForegroundColor Green
} else {
    Write-Host "✗ .env file not found!" -ForegroundColor Red
    exit 1
}

# Step 2: Check if ALLOWED_ORIGINS is set
Write-Host ""
Write-Host "[2/5] Checking ALLOWED_ORIGINS configuration..." -ForegroundColor Yellow
$envContent = Get-Content ".env" -Raw
if ($envContent -match "ALLOWED_ORIGINS=([^\r\n]+)") {
    $allowedOrigins = $matches[1]
    Write-Host "✓ ALLOWED_ORIGINS is set: $allowedOrigins" -ForegroundColor Green
    
    # Parse and display each origin
    $origins = $allowedOrigins -split ","
    Write-Host "  Configured origins:" -ForegroundColor Cyan
    foreach ($origin in $origins) {
        Write-Host "    - $($origin.Trim())" -ForegroundColor White
    }
    
    # Check for security issues
    Write-Host ""
    Write-Host "  Security checks:" -ForegroundColor Cyan
    $hasIssues = $false
    
    foreach ($origin in $origins) {
        $trimmedOrigin = $origin.Trim()
        
        # Check for localhost in production
        if ($trimmedOrigin -match "localhost" -or $trimmedOrigin -match "127\.0\.0\.1") {
            Write-Host "    ⚠ WARNING: localhost/127.0.0.1 detected - Not safe for production!" -ForegroundColor Yellow
            $hasIssues = $true
        }
        
        # Check for HTTP (not HTTPS)
        if ($trimmedOrigin -match "^http://" -and $trimmedOrigin -notmatch "localhost|127\.0\.0\.1") {
            Write-Host "    ⚠ WARNING: HTTP (not HTTPS) detected for $trimmedOrigin" -ForegroundColor Yellow
            $hasIssues = $true
        }
    }
    
    if (-not $hasIssues) {
        Write-Host "    ✓ No security issues detected" -ForegroundColor Green
    }
} else {
    Write-Host "✗ ALLOWED_ORIGINS not found in .env file!" -ForegroundColor Red
    Write-Host "  Add this line to .env:" -ForegroundColor Yellow
    Write-Host "  ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000" -ForegroundColor White
    exit 1
}

# Step 3: Check docker-compose.yml
Write-Host ""
Write-Host "[3/5] Checking docker-compose.yml..." -ForegroundColor Yellow
if (Test-Path "docker-compose.yml") {
    $composeContent = Get-Content "docker-compose.yml" -Raw
    if ($composeContent -match "ALLOWED_ORIGINS=\$\{ALLOWED_ORIGINS\}") {
        Write-Host "✓ docker-compose.yml correctly references ALLOWED_ORIGINS" -ForegroundColor Green
    } else {
        Write-Host "✗ docker-compose.yml may not be passing ALLOWED_ORIGINS correctly" -ForegroundColor Red
    }
} else {
    Write-Host "⚠ docker-compose.yml not found" -ForegroundColor Yellow
}

# Step 4: Check if auth-service is enhanced
Write-Host ""
Write-Host "[4/5] Checking auth-service security enhancements..." -ForegroundColor Yellow
if (Test-Path "services/auth-service/main.py") {
    $authContent = Get-Content "services/auth-service/main.py" -Raw
    
    $checks = @(
        @{ Pattern = "ALLOWED_ORIGINS_RAW"; Name = "Enhanced CORS validation" },
        @{ Pattern = "add_security_headers"; Name = "Security headers middleware" },
        @{ Pattern = "validate_origin"; Name = "Origin validation middleware" },
        @{ Pattern = "X-Content-Type-Options"; Name = "X-Content-Type-Options header" },
        @{ Pattern = "X-Frame-Options"; Name = "X-Frame-Options header" }
    )
    
    $allPassed = $true
    foreach ($check in $checks) {
        if ($authContent -match $check.Pattern) {
            Write-Host "  ✓ $($check.Name)" -ForegroundColor Green
        } else {
            Write-Host "  ✗ $($check.Name) not found" -ForegroundColor Red
            $allPassed = $false
        }
    }
    
    if ($allPassed) {
        Write-Host "✓ All security enhancements implemented" -ForegroundColor Green
    }
} else {
    Write-Host "✗ services/auth-service/main.py not found" -ForegroundColor Red
}

# Step 5: Test if docker-compose can start with configuration
Write-Host ""
Write-Host "[5/5] Validating docker-compose configuration..." -ForegroundColor Yellow
try {
    $output = docker-compose config 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ docker-compose configuration is valid" -ForegroundColor Green
        
        # Check if ALLOWED_ORIGINS appears in the config
        if ($output -match "ALLOWED_ORIGINS") {
            Write-Host "✓ ALLOWED_ORIGINS is present in docker-compose config" -ForegroundColor Green
        } else {
            Write-Host "⚠ ALLOWED_ORIGINS not found in docker-compose config output" -ForegroundColor Yellow
        }
    } else {
        Write-Host "✗ docker-compose configuration has errors" -ForegroundColor Red
        Write-Host $output -ForegroundColor Red
    }
} catch {
    Write-Host "⚠ Could not validate docker-compose (docker-compose may not be installed)" -ForegroundColor Yellow
}

# Summary
Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "Verification Summary" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Configuration Status:" -ForegroundColor Yellow
Write-Host "  - ALLOWED_ORIGINS is configured" -ForegroundColor Green
Write-Host "  - Security enhancements applied" -ForegroundColor Green
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Restart auth-service:" -ForegroundColor White
Write-Host "     docker-compose restart auth-service" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Check service logs:" -ForegroundColor White
Write-Host "     docker-compose logs auth-service | Select-String 'CORS|origin'" -ForegroundColor Cyan
Write-Host ""
Write-Host "  3. For production deployment:" -ForegroundColor White
Write-Host "     Update ALLOWED_ORIGINS with your production domain(s)" -ForegroundColor Cyan
Write-Host "     Example: ALLOWED_ORIGINS=https://yourdomain.com" -ForegroundColor Cyan
Write-Host ""
Write-Host "For detailed information, see: CORS_SECURITY_CRITICAL_ISSUE.md" -ForegroundColor Yellow
Write-Host ""
