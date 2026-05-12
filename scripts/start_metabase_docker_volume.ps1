param(
    [string]$Port = "3000",
    [string]$ContainerName = "rhoonart-metabase-3000",
    [string]$VolumeName = "rhoonart-metabase-data"
)

$ErrorActionPreference = "Stop"

$existingPort = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($existingPort) {
    $pidList = ($existingPort | Select-Object -ExpandProperty OwningProcess -Unique) -join ", "
    throw "Port $Port is already in use by process id(s): $pidList. Stop that process before starting Metabase Docker."
}

wsl -u root -e sh -lc "docker volume inspect $VolumeName >/dev/null"
wsl -u root -e sh -lc "docker rm -f $ContainerName >/dev/null 2>&1 || true"

$dockerRun = "docker run -d --name $ContainerName -p ${Port}:3000 -v ${VolumeName}:/metabase-data -e MB_DB_FILE=/metabase-data/metabase.db -e MAX_SESSION_AGE=525600 -e MB_SESSION_COOKIES=false metabase/metabase:latest"
wsl -u root -e sh -lc $dockerRun

Write-Host "Metabase Docker started at http://localhost:$Port using volume '$VolumeName'."
