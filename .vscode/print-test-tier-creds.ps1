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
Write-Host '  Postgres (test-api)     127.0.0.1:5432' -ForegroundColor $fg
Write-Host '  Postgres (clutterstock) 127.0.0.1:5433' -ForegroundColor $fg
Write-Host '  Valkey     127.0.0.1:6379' -ForegroundColor $fg
Write-Host '  RabbitMQ   127.0.0.1:5672   vhost: test' -ForegroundColor $fg
Write-Host ''

function Write-PgCreds {
    param(
        [string] $Label,
        [string] $Namespace,
        [string] $SecretName,
        [string] $LocalPort
    )
    Write-Host "--- Postgres $Label (secret $SecretName / $Namespace) ---" -ForegroundColor $fy
    $uri  = Get-SecretKey -Namespace $Namespace -Name $SecretName -Key uri
    $user = Get-SecretKey -Namespace $Namespace -Name $SecretName -Key username
    $pass = Get-SecretKey -Namespace $Namespace -Name $SecretName -Key password
    $db   = Get-SecretKey -Namespace $Namespace -Name $SecretName -Key dbname
    if ($uri) {
        $local = $uri -replace '@[^/]+', "@127.0.0.1:$LocalPort"
        Write-Host 'URI (cluster):' -ForegroundColor Gray
        Write-Host $uri
        Write-Host "URI (localhost :$LocalPort):" -ForegroundColor Gray
        Write-Host $local
    } else {
        Write-Host "(could not read $SecretName uri — check context and namespace)" -ForegroundColor Red
    }
    if ($user) { Write-Host 'Username:' -ForegroundColor Gray; Write-Host $user }
    if ($pass) { Write-Host 'Password:' -ForegroundColor Gray; Write-Host $pass }
    if ($db)   { Write-Host 'Database:' -ForegroundColor Gray; Write-Host $db }
    Write-Host ''
}

Write-PgCreds -Label '(test-api)'     -Namespace postgres-test -SecretName testdb-app       -LocalPort 5432
Write-PgCreds -Label '(clutterstock)' -Namespace postgres-test -SecretName cluttertestdb-app -LocalPort 5433

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
