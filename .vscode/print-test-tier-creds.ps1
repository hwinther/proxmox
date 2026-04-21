# Shown before kubectl port-forward tasks — test tier on production cluster.
$fc = 'Cyan'
$fy = 'Yellow'
Write-Host ''
Write-Host '=== Test tier — authenticate via localhost (ports forwarded by the next tasks) ===' -ForegroundColor $fc
Write-Host ''
Write-Host '  Postgres   127.0.0.1:5432   (db usually api; replace host in URI from secret)' -ForegroundColor Gray
Write-Host '  Valkey     127.0.0.1:6379   (redis:// URL with password)' -ForegroundColor Gray
Write-Host '  RabbitMQ   127.0.0.1:5672   virtual host: test' -ForegroundColor Gray
Write-Host ''
Write-Host '-- Postgres: full URI (point at 127.0.0.1:5432)' -ForegroundColor $fy
Write-Host @'
kubectl get secret testdb-app -n postgres-test -o jsonpath='{.data.uri}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
'@
Write-Host ''
Write-Host '-- Postgres: username / password / dbname' -ForegroundColor $fy
Write-Host @'
kubectl get secret testdb-app -n postgres-test -o jsonpath='{.data.username}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
kubectl get secret testdb-app -n postgres-test -o jsonpath='{.data.password}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
kubectl get secret testdb-app -n postgres-test -o jsonpath='{.data.dbname}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
'@
Write-Host ''
Write-Host '-- Valkey: password (shared-test)' -ForegroundColor $fy
Write-Host @'
kubectl get secret valkey-auth -n shared-test -o jsonpath='{.data.password}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
'@
Write-Host ''
Write-Host '-- Valkey: optional full redis-url from test-frontend (swap host for 127.0.0.1:6379)' -ForegroundColor $fy
Write-Host @'
kubectl get secret test-frontend-valkey -n test-test -o jsonpath='{.data.redis-url}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
'@
Write-Host ''
Write-Host '-- RabbitMQ: username / password (vhost test)' -ForegroundColor $fy
Write-Host @'
kubectl get secret test-api-rabbitmq -n test-test -o jsonpath='{.data.username}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
kubectl get secret test-api-rabbitmq -n test-test -o jsonpath='{.data.password}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
'@
Write-Host ''
Write-Host 'Starting port-forwards in other terminals...' -ForegroundColor $fc
Write-Host ''
