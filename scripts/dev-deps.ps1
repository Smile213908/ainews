# 开发依赖一键拉起：PostgreSQL 16 + Redis 7（docker compose）
# 已在运行会自动跳过；首次运行自动创建 pgdata / redisdata 卷。
# 用法：  powershell -File scripts/dev-deps.ps1
#        停止：docker compose stop db redis
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

docker compose up -d db redis
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "等待 PostgreSQL / Redis 就绪…"
$deadline = (Get-Date).AddSeconds(60)
while ((Get-Date) -lt $deadline) {
    docker compose exec -T db pg_isready -U hotmonitor *> $null
    $pgOk = ($LASTEXITCODE -eq 0)
    docker compose exec -T redis redis-cli ping *> $null
    $redisOk = ($LASTEXITCODE -eq 0)
    if ($pgOk -and $redisOk) {
        Write-Host "依赖就绪：PG localhost:5432 / Redis localhost:6379（端口以 .env 的 DB_PORT / REDIS_PORT 为准）"
        exit 0
    }
    Start-Sleep -Seconds 2
}
Write-Warning "等待超时，请执行 docker compose ps 查看状态"
exit 1
