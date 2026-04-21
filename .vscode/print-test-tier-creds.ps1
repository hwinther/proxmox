# Runs before port-forward tasks: fetches test-tier secrets via kubectl and prints decoded values.

function Get-SecretKey {
    param(
        [string] $Namespace,
        [string] $Name,
        [string] $Key
    )
    $b64 = & kubectl get secret $Name -n $Namespace -o jsonpath="{.data.$Key}" 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($b64)) { return $null }
    try {
        [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($b64))
    } catch {
        return $null
    }
}

function Require-Kubectl {
    if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) {
        Write-Host 'kubectl not found on PATH.' -ForegroundColor Red
        exit 1
    }
}

Require-Kubectl

$fc = 'Cyan'
$fy = 'Yellow'
$fg = 'Gray'

Write-Host ''
Write-Host '=== Test tier — values for localhost (use with forwarded ports) ===' -ForegroundColor $fc
Write-Host ''
Write-Host '  Postgres   127.0.0.1:5432' -ForegroundColor $fg
Write-Host '  Valkey     127.0.0.1:6379' -ForegroundColor $fg
Write-Host '  RabbitMQ   127.0.0.1:5672   vhost: test' -ForegroundColor $fg
Write-Host ''

# --- Postgres (testdb-app) ---
Write-Host '--- Postgres (secret testdb-app / postgres-test) ---' -ForegroundColor $fy
$pgUri = Get-SecretKey -Namespace postgres-test -Name testdb-app -Key uri
$pgUser = Get-SecretKey -Namespace postgres-test -Name testdb-app -Key username
$pgPass = Get-SecretKey -Namespace postgres-test -Name testdb-app -Key password
$pgDb = Get-SecretKey -Namespace postgres-test -Name testdb-app -Key dbname
if ($pgUri) {
    $pgLocal = $pgUri -replace '@[^/]+', '@127.0.0.1:5432'
    Write-Host 'ConnectionStrings__Blogging (cluster URI):' -ForegroundColor Gray
    Write-Host $pgUri
    Write-Host 'ConnectionStrings__Blogging (localhost, paste into appsettings / env):' -ForegroundColor Gray
    Write-Host $pgLocal
} else {
    Write-Host '(could not read testdb-app uri — check context and namespace)' -ForegroundColor Red
}
if ($pgUser) {
    Write-Host 'Postgres username:' -ForegroundColor Gray
    Write-Host $pgUser
}
if ($pgPass) {
    Write-Host 'Postgres password:' -ForegroundColor Gray
    Write-Host $pgPass
}
if ($pgDb) {
    Write-Host 'Postgres database:' -ForegroundColor Gray
    Write-Host $pgDb
}
Write-Host ''

# --- Valkey ---
Write-Host '--- Valkey (secret valkey-auth / shared-test) ---' -ForegroundColor $fy
$vkPass = Get-SecretKey -Namespace shared-test -Name valkey-auth -Key password
if ($vkPass) {
    Write-Host 'Valkey password:' -ForegroundColor Gray
    Write-Host $vkPass
    $enc = [Uri]::EscapeDataString($vkPass)
    $redisLocal = "redis://:$enc@127.0.0.1:6379/0"
    Write-Host 'REDIS_URL (localhost, password URL-encoded):' -ForegroundColor Gray
    Write-Host $redisLocal
} else {
    Write-Host '(could not read valkey-auth password)' -ForegroundColor Red
}
$feUrl = Get-SecretKey -Namespace test-test -Name test-frontend-valkey -Key 'redis-url'
if ($feUrl) {
    Write-Host 'redis-url from test-frontend-valkey (cluster host, for reference):' -ForegroundColor Gray
    Write-Host $feUrl
}
Write-Host ''

# --- RabbitMQ ---
Write-Host '--- RabbitMQ (secret test-api-rabbitmq / test-test) vhost: test ---' -ForegroundColor $fy
$rmqUser = Get-SecretKey -Namespace test-test -Name test-api-rabbitmq -Key username
$rmqPass = Get-SecretKey -Namespace test-test -Name test-api-rabbitmq -Key password
if ($rmqUser) {
    Write-Host 'RabbitMq__UserName:' -ForegroundColor Gray
    Write-Host $rmqUser
}
if ($rmqPass) {
    Write-Host 'RabbitMq__Password:' -ForegroundColor Gray
    Write-Host $rmqPass
}
if (-not $rmqUser -and -not $rmqPass) {
    Write-Host '(could not read test-api-rabbitmq)' -ForegroundColor Red
}
Write-Host 'RabbitMq__HostName (local):' -ForegroundColor Gray
Write-Host '127.0.0.1'
Write-Host 'RabbitMq__VirtualHost:' -ForegroundColor Gray
Write-Host 'test'
Write-Host ''

Write-Host 'Starting port-forwards in other terminals...' -ForegroundColor $fc
Write-Host ''
