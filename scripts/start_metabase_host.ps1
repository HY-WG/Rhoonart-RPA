param(
    [string]$Port = "3001"
)

$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
$Java = Join-Path $Root ".local-tools\java\jdk-21.0.11+10-jre\bin\java.exe"
$MetabaseJar = Join-Path $Root ".local-tools\metabase\metabase.jar"

$env:MB_JETTY_PORT = $Port
$env:MAX_SESSION_AGE = "525600"
$env:MB_SESSION_COOKIES = "false"
Remove-Item Env:\MB_SESSION_TIMEOUT -ErrorAction SilentlyContinue

& $Java -jar $MetabaseJar
