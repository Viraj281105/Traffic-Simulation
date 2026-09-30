<#
.SYNOPSIS
    UrbanFlow development orchestrator. Needs only Docker and Git on the host.

.DESCRIPTION
    Builds and runs the full stack from docker-compose.yml: the backend image
    (FastAPI + simulation engine) and the frontend image (production build
    served by nginx, which proxies /api, /ws and /health to the backend).
    SQLite lives in the named volume "<project>_traffic_data", which this
    script never removes unless -Clean -DeleteData is given explicitly.

    Change detection is Docker's own: every start runs `docker compose build`,
    whose BuildKit cache is keyed on the exact files each image copies, so an
    unchanged service is a cache hit (no rebuild), and `docker compose up`
    recreates a container only when its image or configuration changed.

    -Dev runs docker-compose.dev.yml instead: the Vite dev server (port 5173)
    and uvicorn --reload (port 8000) in containers, with the source
    bind-mounted so edits apply live, the development sign-in on, and its own
    database volume. Its images hold only dependencies, so they rebuild only
    when requirements.txt or package*.json change. -Dev combines with every
    other switch (e.g. .\start.ps1 -Dev -Logs frontend). Production and
    development share one Compose project, so starting one replaces the other.

.EXAMPLE
    .\start.ps1                 Build what changed, start, wait for health, smoke test
    .\start.ps1 -Status         Read-only report of containers, images, database and source
    .\start.ps1 -Logs [backend] Follow logs (all services, or one)
    .\start.ps1 -Restart        Recreate containers from the current images (data kept)
    .\start.ps1 -Rebuild        Rebuild images without cache, then start
    .\start.ps1 -SmokeTest      Check the running stack end to end
    .\start.ps1 -Clean          Remove containers and images of both stacks (database volumes kept)
    .\start.ps1 -Clean -DeleteData   ...and also delete the database volume (asks first)
    .\start.ps1 -Dev            Development stack with hot reload (add to any of the above)
#>
[CmdletBinding(DefaultParameterSetName = 'Up')]
param(
    [Parameter(ParameterSetName = 'Status')] [switch]$Status,
    [Parameter(ParameterSetName = 'Logs')] [switch]$Logs,
    [Parameter(ParameterSetName = 'Logs', Position = 0)]
    [ValidateSet('backend', 'frontend')] [string]$Service,
    [Parameter(ParameterSetName = 'Restart')] [switch]$Restart,
    [Parameter(ParameterSetName = 'Rebuild')] [switch]$Rebuild,
    [Parameter(ParameterSetName = 'SmokeTest')] [switch]$SmokeTest,
    [Parameter(ParameterSetName = 'Clean')] [switch]$Clean,
    [Parameter(ParameterSetName = 'Clean')] [switch]$DeleteData,
    [Parameter(ParameterSetName = 'Clean')] [switch]$Force,
    [Parameter(ParameterSetName = 'Up')]
    [Parameter(ParameterSetName = 'Restart')]
    [Parameter(ParameterSetName = 'Rebuild')] [switch]$NoBrowser,
    [switch]$Dev
)

# Native tools (docker, git) report progress on stderr; with 'Stop', Windows
# PowerShell 5.1 would turn that into terminating errors. Every native call's
# exit code is checked explicitly instead.
$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root

# -Dev: every Compose call uses the development file (passed as -f rather than
# through COMPOSE_FILE, which would leak into the caller's session).
$ComposeFile = if ($Dev) { 'docker-compose.dev.yml' } else { $null }
$StackName = if ($Dev) { 'development' } else { 'production' }
$Services = @('backend', 'frontend')
$HealthTimeoutSeconds = 180
# Everything backend/Dockerfile copies into the image. The backend's recorded
# commit is the last one that changed these, so a docs-only commit does not
# rebuild it (see Get-Provenance).
$BackendInputs = @('backend/src', 'backend/requirements.txt', 'backend/Dockerfile',
    'backend/docker-entrypoint.py', 'shared', '.dockerignore')

# -- Output ----------------------------------------------------------------

$script:StepNo = 0
$script:StepTotal = 0
function Step([string]$Title) {
    $script:StepNo++
    Write-Host ''
    Write-Host ("[{0}/{1}] {2}" -f $script:StepNo, $script:StepTotal, $Title) -ForegroundColor Cyan
}
function Ok([string]$Text) { Write-Host "  [ok] $Text" -ForegroundColor Green }
function Info([string]$Text) { Write-Host "  $Text" }
function Warn([string]$Text) { Write-Host "  [warn] $Text" -ForegroundColor Yellow }
function Fail([string]$Text, [string[]]$Hints = @()) {
    Write-Host "  [fail] $Text" -ForegroundColor Red
    foreach ($h in $Hints) { Write-Host "         $h" -ForegroundColor Red }
    exit 1
}

# -- Native command helpers -----------------------------------------------

# Runs docker.exe and returns its output lines (stdout and stderr), with the exit
# code in $LASTEXITCODE.
function Invoke-Docker {
    $a = Add-ComposeFile $args
    $out = & docker @a 2>&1 | ForEach-Object { "$_" }
    return $out
}

function Add-ComposeFile([object[]]$Arguments) {
    if ($ComposeFile -and $Arguments.Count -gt 0 -and $Arguments[0] -eq 'compose') {
        return @('compose', '-f', $ComposeFile) + @($Arguments | Select-Object -Skip 1)
    }
    return $Arguments
}

function Test-DockerDaemon {
    $null = & docker version --format '{{.Server.Version}}' 2>&1
    return $LASTEXITCODE -eq 0
}

$script:Project = $null
function Get-ComposeModel {
    $json = Invoke-Docker compose config --format json
    if ($LASTEXITCODE -ne 0) {
        Fail 'docker-compose.yml is not valid for this environment:' ($json | Select-Object -Last 8)
    }
    $model = ($json -join "`n") | ConvertFrom-Json
    $script:Project = $model.name
    $script:Model = $model
    return $model
}

# The image tag Compose builds for a service: its `image:` (the dev file sets
# one), else Compose's default "<project>-<service>".
function Get-ImageName([string]$Svc) {
    $svcModel = $script:Model.services.$Svc
    if ($svcModel -and $svcModel.PSObject.Properties['image'] -and $svcModel.image) { return $svcModel.image }
    return "$script:Project-$Svc"
}

# Which stack a container belongs to, from the Compose file that created it.
function Get-StackOf($c) {
    if (-not $c) { return $null }
    $files = "$($c.Config.Labels.'com.docker.compose.project.config_files')"
    if ($files -match 'docker-compose\.dev\.yml') { return 'development' }
    return 'production'
}

# `docker inspect` of every container of this project, by service name. Found
# through Compose's own labels with plain docker calls, which are several
# times faster than `docker compose ps` on Windows.
function Get-Containers {
    $map = @{}
    $ids = @(Invoke-Docker ps -a -q --filter "label=com.docker.compose.project=$script:Project" | Where-Object { $_ })
    if ($LASTEXITCODE -ne 0 -or $ids.Count -eq 0) { return $map }
    $json = Invoke-Docker inspect @ids
    if ($LASTEXITCODE -ne 0) { return $map }
    foreach ($c in (($json -join "`n") | ConvertFrom-Json)) {
        $svc = $c.Config.Labels.'com.docker.compose.service'
        if ($svc -and $c.Config.Labels.'com.docker.compose.oneoff' -ne 'True') { $map[$svc] = $c }
    }
    return $map
}

function Get-Container([string]$Svc) { return (Get-Containers)[$Svc] }

function Get-ImageId([string]$Name) {
    $id = Invoke-Docker image inspect --format '{{.Id}}' $Name
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($id | Select-Object -First 1)
}

# The image a container actually runs. On Docker's containerd image store
# that is its platform manifest (ImageManifestDescriptor); .Image can name the
# multi-platform index it was created from. The classic store has only .Image.
function Get-RunningImage($c) {
    if (-not $c) { return $null }
    if ($c.PSObject.Properties['ImageManifestDescriptor'] -and $c.ImageManifestDescriptor) {
        return $c.ImageManifestDescriptor.digest
    }
    return $c.Image
}

function Get-ContainerState($c) {
    if (-not $c) { return 'missing' }
    $health = if ($c.State.PSObject.Properties['Health'] -and $c.State.Health) { $c.State.Health.Status } else { 'none' }
    if ($c.State.Status -eq 'running' -and $health -ne 'none') { return $health }
    return $c.State.Status
}

function Short([string]$Id) {
    if (-not $Id) { return '-' }
    return ($Id -replace '^sha256:', '').Substring(0, [Math]::Min(12, ($Id -replace '^sha256:', '').Length))
}

# -- Docker availability --------------------------------------------------

function Assert-Docker([switch]$AllowStart) {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Fail 'docker was not found on PATH.' @('Install Docker Desktop: https://docs.docker.com/desktop/')
    }
    if (-not (Test-DockerDaemon)) {
        $desktop = @("$env:LOCALAPPDATA\Programs\DockerDesktop\Docker Desktop.exe",
            "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe") |
            Where-Object { Test-Path $_ } | Select-Object -First 1
        if (-not ($AllowStart -and $desktop)) {
            Fail 'The Docker engine is not running.' @('Start Docker Desktop, then run this again.')
        }
        Info 'Docker engine is not running; starting Docker Desktop...'
        Start-Process $desktop
        $deadline = (Get-Date).AddSeconds(180)
        while (-not (Test-DockerDaemon)) {
            if ((Get-Date) -gt $deadline) {
                Fail 'Docker Desktop did not become ready within 3 minutes.' @('Open Docker Desktop and check for errors, then run this again.')
            }
            Start-Sleep -Seconds 3
        }
    }
    $engine = (Invoke-Docker version --format '{{.Server.Version}}') | Select-Object -First 1
    $compose = (Invoke-Docker compose version --short) | Select-Object -First 1
    if ($LASTEXITCODE -ne 0) {
        Fail 'Docker Compose v2 is not available (`docker compose`).' @('Update Docker Desktop.')
    }
    $cv = [version](($compose -replace '^v', '') -replace '[^0-9.].*$', '')
    if ($cv -lt [version]'2.20') {
        Fail "Docker Compose $compose is too old (2.20 or later is needed)." @('Update Docker Desktop.')
    }
    Ok "Docker engine $engine, Compose $compose"
}

# -- Environment ----------------------------------------------------------

# The variables docker-compose.yml reads, with their checks. Values come from
# the shell or the project .env file (Compose's own precedence: shell wins).
function Read-DotEnv([string]$Path) {
    $vars = @{}
    if (-not (Test-Path $Path)) { return $vars }
    $n = 0
    foreach ($line in Get-Content $Path) {
        $n++
        $t = $line.Trim()
        if ($t -eq '' -or $t.StartsWith('#')) { continue }
        if ($t -notmatch '^(export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') {
            Fail ".env line $n is not KEY=VALUE: '$t'" @("Fix or remove the line in $Path.")
        }
        $vars[$Matches[2]] = $Matches[3].Trim().Trim('"').Trim("'")
    }
    return $vars
}

function Test-Environment {
    $dotenv = Read-DotEnv (Join-Path $Root '.env')
    if ($dotenv.Count -gt 0) { Info ".env: $($dotenv.Keys.Count) variable(s) ($((@($dotenv.Keys) | Sort-Object) -join ', '))" }
    function Value([string]$Name) {
        $v = [Environment]::GetEnvironmentVariable($Name)
        if ($null -ne $v) { return $v }
        if ($dotenv.ContainsKey($Name)) { return $dotenv[$Name] }
        return $null
    }
    $problems = @()

    $ports = @{}
    foreach ($spec in @(@('URBANFLOW_HTTP_PORT', 80), @('URBANFLOW_ALT_HTTP_PORT', 3000))) {
        $v = Value $spec[0]
        if ([string]::IsNullOrEmpty($v)) { $ports[$spec[0]] = $spec[1]; continue }
        $p = 0
        if (-not [int]::TryParse($v, [ref]$p) -or $p -lt 1 -or $p -gt 65535) {
            $problems += "$($spec[0])='$v' must be a port number (1-65535)."
        }
        $ports[$spec[0]] = $p
    }
    if ($ports['URBANFLOW_HTTP_PORT'] -eq $ports['URBANFLOW_ALT_HTTP_PORT']) {
        $problems += 'URBANFLOW_HTTP_PORT and URBANFLOW_ALT_HTTP_PORT must differ.'
    }

    $workers = Value 'STUDY_WORKERS'
    if (-not [string]::IsNullOrEmpty($workers)) {
        $w = 0
        if (-not [int]::TryParse($workers, [ref]$w) -or $w -lt 0 -or $w -gt 32) {
            $problems += "STUDY_WORKERS='$workers' must be a whole number from 0 to 32 (empty = one per CPU)."
        }
    }

    $apiKey = Value 'API_KEY'
    if (-not [string]::IsNullOrEmpty($apiKey)) {
        if ($apiKey -match '\s') { $problems += 'API_KEY must not contain whitespace.' }
        elseif ($apiKey.Length -lt 16) { Warn 'API_KEY is shorter than 16 characters; use a random value in shared deployments.' }
        else { Ok 'API_KEY set (mutating/compute endpoints require it; nginx adds it for the app)' }
    }

    $cors = Value 'CORS_ORIGINS'
    if (-not [string]::IsNullOrEmpty($cors) -and $cors -ne '*') {
        foreach ($o in $cors.Split(',')) {
            if ($o.Trim() -notmatch '^https?://[^/\s]+$') {
                $problems += "CORS_ORIGINS entry '$($o.Trim())' must look like http(s)://host[:port] (no path)."
            }
        }
    }

    if ($problems.Count -gt 0) {
        Fail 'Invalid configuration:' ($problems + 'Set these in the shell or in .env next to docker-compose.yml.')
    }

    # Compose itself resolves every ${VAR} (including required ${VAR:?msg}
    # ones) - a failure here names the variable.
    $model = Get-ComposeModel
    Ok "Compose configuration valid ($StackName stack, project '$($model.name)')"
    if ($Dev) { Ok 'Sign-in: development bypass on (signed in as "Local developer"; saving runs works)' }
    else { Info 'Sign-in: Cognito is not configured for the Docker build, so the app runs signed out (saving runs needs sign-in; use -Dev locally).' }
    $published = @($model.services.PSObject.Properties | ForEach-Object { @($_.Value.ports) | Where-Object { $_ } | ForEach-Object { [int]$_.published } } | Select-Object -Unique)
    return @{ Model = $model; HttpPort = [int](@($model.services.frontend.ports)[0].published); Ports = $published }
}

# -- Ports ----------------------------------------------------------------

function Get-PublishedPorts($c) {
    $ports = @()
    if ($c -and $c.State.Status -eq 'running' -and $c.NetworkSettings.Ports) {
        foreach ($binding in $c.NetworkSettings.Ports.PSObject.Properties) {
            foreach ($b in @($binding.Value)) { if ($b) { $ports += [int]$b.HostPort } }
        }
    }
    return $ports | Select-Object -Unique
}

function Test-Ports([int[]]$Ports) {
    $ours = @()
    foreach ($c in (Get-Containers).Values) { $ours += Get-PublishedPorts $c }
    foreach ($port in $Ports) {
        if ($ours -contains $port) { Ok "Port $port is served by this stack"; continue }
        $listener = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
        if (-not $listener) { Ok "Port $port free"; continue }
        $proc = Get-Process -Id $listener.OwningProcess -ErrorAction SilentlyContinue
        $owner = if ($proc) { "$($proc.ProcessName) (PID $($proc.Id))" } else { "PID $($listener.OwningProcess)" }
        if ($proc -and $proc.ProcessName -match 'docker|wslrelay|vpnkit') {
            $other = (Invoke-Docker ps --filter "publish=$port" --format '{{.Names}}') -join ', '
            if ($other) { $owner = "Docker container(s) $other" }
        }
        elseif ($listener.OwningProcess -eq 4) {
            $owner = 'Windows HTTP.sys (PID 4: IIS, World Wide Web Publishing or another http.sys service)'
        }
        $hint = if ($Dev) { @('Stop it (e.g. a native uvicorn or npm run dev) and run this again; the dev ports are set in docker-compose.dev.yml.') }
        else { @('Stop that process/container, or choose other host ports, e.g.:', '  $env:URBANFLOW_HTTP_PORT = 8080; $env:URBANFLOW_ALT_HTTP_PORT = 3001; .\start.ps1') }
        Fail "Port $port is already in use by $owner." $hint
    }
}

# -- Source provenance ----------------------------------------------------

function Get-Provenance {
    $p = @{ Branch = '?'; Commit = 'unknown'; Dirty = @(); BackendCommit = ''; BackendDirty = $false; HasGit = $false }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { return $p }
    $head = (& git rev-parse HEAD 2>$null)
    if ($LASTEXITCODE -ne 0) { return $p }
    $p.HasGit = $true
    $p.Commit = "$head".Trim()
    $p.Branch = "$(& git rev-parse --abbrev-ref HEAD 2>$null)".Trim()
    $p.Dirty = @(& git status --porcelain 2>$null | Where-Object { $_ })
    $p.BackendCommit = "$(& git log -1 --format=%H -- @BackendInputs 2>$null)".Trim()
    $p.BackendDirty = [bool](@(& git status --porcelain -- @BackendInputs 2>$null | Where-Object { $_ }).Count)
    return $p
}

# What the backend image should report as its commit (GIT_COMMIT build arg):
# the last commit that changed its inputs, or none when those have
# uncommitted edits - saved runs then honestly record "unknown".
function Get-ExpectedBackendCommit($prov) {
    if (-not $prov.HasGit -or $prov.BackendDirty -or -not $prov.BackendCommit) { return 'unknown' }
    return $prov.BackendCommit
}

function Show-Provenance($prov) {
    if (-not $prov.HasGit) { Warn 'Not a git checkout; the build is recorded as version "unknown".'; return }
    $state = if ($prov.Dirty.Count -eq 0) { 'clean' } else { "dirty ($($prov.Dirty.Count) changed file(s))" }
    Info "Branch:  $($prov.Branch)"
    Info "Commit:  $($prov.Commit.Substring(0, 12))  (working tree $state)"
    if ($prov.Dirty.Count -gt 0) {
        $groups = $prov.Dirty | ForEach-Object {
            $path = ($_.Substring(3) -split ' -> ')[-1].Trim('"')
            if ($path -match '^(backend/src|shared)/|^backend/(requirements\.txt|Dockerfile|docker-entrypoint\.py)$') { 'backend' }
            elseif ($path -match '^frontend/src/test/|\.test\.tsx?$') { 'tests' }
            elseif ($path -match '^frontend/') { 'frontend' }
            elseif ($path -match '^(docker-compose.*\.yml|\.dockerignore|\.env)$') { 'compose/env' }
            elseif ($path -match '^backend/tests/') { 'tests' }
            else { 'docs/other' }
        } | Group-Object | ForEach-Object { "$($_.Count) $($_.Name)" }
        Info "Changes: $($groups -join ', ')"
    }
}

# -- Build, containers, health --------------------------------------------

function Invoke-Build($project, [switch]$NoCache) {
    $before = @{}
    foreach ($s in $Services) { $before[$s] = Get-ImageId (Get-ImageName $s) }
    # No default provenance attestation: it is timestamped on every build, so
    # an otherwise fully cached build would get a new image ID and look
    # changed. The image content and cache are unaffected.
    $env:BUILDX_NO_DEFAULT_ATTESTATIONS = '1'
    $buildArgs = @('compose', 'build', '--progress', 'plain')
    if ($NoCache) { $buildArgs += '--no-cache' }
    $log = New-Object System.Collections.Generic.List[string]
    $headers = @{}   # BuildKit step number -> "[stage] RUN/COPY ..." awaiting its outcome
    $worked = @{}    # services with at least one step that was not cached
    $started = Get-Date
    # List each build step that actually runs; cached steps stay quiet.
    # (--progress plain prints "#N [stage] COPY ..." then either "#N CACHED"
    # or the step's own output / "#N DONE".)
    $buildArgs = Add-ComposeFile $buildArgs
    & docker @buildArgs 2>&1 | ForEach-Object {
        $line = "$_"
        $log.Add($line)
        if ($line -match '^#(\d+) (\[\w+[^\]]*\] (RUN|COPY) .*)$') { $headers[$Matches[1]] = $Matches[2] }
        elseif ($line -match '^#(\d+) (CACHED|DONE|\d+\.\d+ )' -and $headers.ContainsKey($Matches[1])) {
            if ($Matches[2] -ne 'CACHED') {
                Write-Host "    $($headers[$Matches[1]])" -ForegroundColor DarkGray
                $worked[($headers[$Matches[1]] -replace '^\[(\w+).*$', '$1')] = $true
            }
            $headers.Remove($Matches[1])
        }
    }
    if ($LASTEXITCODE -ne 0) {
        Write-Host ($log | Select-Object -Last 30 | Out-String) -ForegroundColor DarkGray
        Fail 'Image build failed (output above).'
    }
    $secs = [int]((Get-Date) - $started).TotalSeconds
    $changed = @()
    foreach ($s in $Services) {
        $after = Get-ImageId (Get-ImageName $s)
        if ($before[$s] -ne $after) { $changed += $s }
        if (-not $before[$s]) { Ok "$s built (new image $(Short $after))" }
        elseif ($NoCache) { Ok "$s rebuilt from scratch (image $(Short $after))" }
        elseif ($before[$s] -ne $after) { Ok "$s rebuilt: its sources changed (image $(Short $after))" }
        elseif ($worked[$s]) { Ok "$s unchanged: build steps re-ran but produced an identical image" }
        else { Ok "$s unchanged: build cache hit, nothing rebuilt" }
    }
    Info "Build step: ${secs}s"
    return , $changed
}

function Start-Containers([switch]$ForceRecreate, [string[]]$RebuiltImages = @()) {
    $before = @{}
    $wasRunning = @{}
    $recreate = @()
    $containers = Get-Containers
    foreach ($s in $Services) {
        $c = $containers[$s]
        $before[$s] = if ($c) { $c.Id } else { $null }
        $wasRunning[$s] = $c -and $c.State.Status -eq 'running'
        $state = Get-ContainerState $c
        if ($state -eq 'unhealthy') { Warn "$s is unhealthy; it will be recreated"; $recreate += $s }
        elseif ($state -notin @('healthy', 'starting', 'missing')) { Info "$s is $state" }
    }
    Info 'Starting containers (the frontend starts once the backend is healthy)...'
    # Unhealthy ones first: Compose will not start the frontend while the
    # backend it depends on is unhealthy.
    if ($recreate.Count -gt 0 -and -not $ForceRecreate) {
        $out = Invoke-Docker compose up -d --no-build --no-deps --force-recreate @recreate
        if ($LASTEXITCODE -ne 0) {
            Show-Diagnostics
            Fail 'Recreating unhealthy services failed:' ($out | Select-Object -Last 6)
        }
    }
    $upArgs = @('compose', 'up', '-d', '--no-build', '--remove-orphans')
    if ($ForceRecreate) { $upArgs += '--force-recreate' }
    # A rebuilt dev frontend image has new dependencies: take node_modules from
    # it rather than from the previous container's anonymous volume.
    if ($Dev -and ($RebuiltImages -contains 'frontend' -or $ForceRecreate)) { $upArgs += '--renew-anon-volumes' }
    $out = Invoke-Docker @upArgs
    if ($LASTEXITCODE -ne 0) {
        Show-Diagnostics
        Fail 'docker compose up failed:' ($out | Select-Object -Last 6)
    }
    $containers = Get-Containers
    foreach ($s in $Services) {
        $c = $containers[$s]
        if (-not $before[$s]) { Ok "$s created" }
        elseif ($before[$s] -ne $c.Id -and $recreate -contains $s) { Ok "$s recreated (it was unhealthy)" }
        elseif ($before[$s] -ne $c.Id -and $ForceRecreate) { Ok "$s recreated (-Restart)" }
        elseif ($before[$s] -ne $c.Id) { Ok "$s recreated (new image or configuration)" }
        elseif (-not $wasRunning[$s]) { Ok "$s started (its container was stopped)" }
        else { Ok "$s kept (already up to date)" }
    }
}

function Show-Diagnostics {
    $containers = Get-Containers
    foreach ($s in $Services) {
        $c = $containers[$s]
        $state = Get-ContainerState $c
        if ($state -in @('healthy', 'missing')) { continue }
        Write-Host "  --- $s ($state): last health checks and logs ---" -ForegroundColor Yellow
        if ($c -and $c.State.PSObject.Properties['Health'] -and $c.State.Health) {
            $c.State.Health.Log | Select-Object -Last 2 | ForEach-Object { Write-Host "    health: exit $($_.ExitCode) $("$($_.Output)".Trim())" -ForegroundColor DarkGray }
        }
        Invoke-Docker compose logs --tail 25 $s | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
    }
}

function Wait-Healthy {
    $deadline = (Get-Date).AddSeconds($HealthTimeoutSeconds)
    $retried = @{}
    $last = ''
    while ($true) {
        $states = @{}
        $containers = Get-Containers
        foreach ($s in $Services) { $states[$s] = Get-ContainerState $containers[$s] }
        $summary = ($Services | ForEach-Object { "$_=$($states[$_])" }) -join '  '
        if ($summary -ne $last) { Info $summary; $last = $summary }
        if (@($Services | Where-Object { $states[$_] -ne 'healthy' }).Count -eq 0) { Ok 'All services healthy'; return }
        foreach ($s in $Services) {
            if ($states[$s] -in @('unhealthy', 'exited', 'dead', 'missing') -and -not $retried[$s]) {
                # One automatic recreate; a second failure is reported.
                Warn "$s is $($states[$s]); recreating it once"
                Show-Diagnostics
                $retried[$s] = $true
                $null = Invoke-Docker compose up -d --no-build --force-recreate $s
            }
            elseif ($states[$s] -in @('unhealthy', 'exited', 'dead', 'missing')) {
                Show-Diagnostics
                Fail "$s is still $($states[$s]) after being recreated." @("Inspect with: .\start.ps1 -Logs $s")
            }
        }
        if ((Get-Date) -gt $deadline) {
            Show-Diagnostics
            Fail "Services were not healthy within $HealthTimeoutSeconds s." @('Inspect with: .\start.ps1 -Logs')
        }
        Start-Sleep -Seconds 2
    }
}

# -- Database -------------------------------------------------------------

# The named volume mounted at the backend's /app/data, as Compose names it.
function Get-VolumeName($model) {
    $m = @($model.services.backend.volumes | Where-Object { $_.target -eq '/app/data' })[0]
    if ($m -and $m.type -eq 'volume') {
        $top = $model.volumes.($m.source)
        if ($top -and $top.PSObject.Properties['name'] -and $top.name) { return $top.name }
        return "$($model.name)_$($m.source)"
    }
    return "$($model.name)_traffic_data"
}

function Test-VolumeExists([string]$Name) {
    $null = Invoke-Docker volume inspect $Name
    return $LASTEXITCODE -eq 0
}

# Read-only look at the database through the running backend container.
function Get-DatabaseInfo {
    $py = "import json,os,sqlite3;p=os.environ['DB_PATH'];e=os.path.exists(p);" +
    "c=sqlite3.connect('file:'+p+'?mode=ro',uri=True) if e else None;" +
    "q=lambda t:c.execute('select count(*) from '+t).fetchone()[0];" +
    "print(json.dumps({'path':p,'exists':e,'bytes':os.path.getsize(p) if e else 0," +
    "'runs':q('simulation_runs') if e else 0,'sweeps':q('sweep_sessions') if e else 0}))"
    $out = Invoke-Docker compose exec -T backend python -c $py
    if ($LASTEXITCODE -ne 0) { return $null }
    return ($out | Select-Object -Last 1) | ConvertFrom-Json
}

function Test-Database($model, [bool]$WasNew) {
    $volume = Get-VolumeName $model
    $c = Get-Container 'backend'
    $mount = @($c.Mounts | Where-Object { $_.Destination -eq '/app/data' })[0]
    if (-not $mount -or $mount.Type -ne 'volume' -or $mount.Name -ne $volume) {
        Fail "The backend's /app/data is not the named volume '$volume'; data would not persist." @('Check the volumes: section of docker-compose.yml.')
    }
    $db = Get-DatabaseInfo
    if (-not $db -or -not $db.exists) { Fail "Database file not found in the backend container ($volume)." }
    $size = '{0:N1} MB' -f ($db.bytes / 1MB)
    if ($WasNew) { Ok "Database: new volume '$volume' initialised ($size)" }
    else { Ok "Database: existing volume '$volume' ($($db.runs) saved runs, $($db.sweeps) sweeps, $size)" }
}

# -- Smoke test -----------------------------------------------------------

function Get-Http([string]$Url, [switch]$Page) {
    # Pages are requested as a browser navigates (Accept: text/html): the Vite
    # dev server serves app.html for dashboard routes only to such requests.
    $headers = if ($Page) { @{ Accept = 'text/html' } } else { @{} }
    try { return Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 30 -Headers $headers }
    catch { return $null }
}

function Receive-WebSocketFrame([string]$Url) {
    $ws = New-Object System.Net.WebSockets.ClientWebSocket
    $cts = New-Object System.Threading.CancellationTokenSource 10000
    try {
        $ws.ConnectAsync([Uri]$Url, $cts.Token).GetAwaiter().GetResult()
        $buffer = New-Object byte[] 65536
        $segment = New-Object 'System.ArraySegment[byte]' -ArgumentList @(, $buffer)
        $text = New-Object System.Text.StringBuilder
        do {
            $r = $ws.ReceiveAsync($segment, $cts.Token).GetAwaiter().GetResult()
            [void]$text.Append([Text.Encoding]::UTF8.GetString($buffer, 0, $r.Count))
        } until ($r.EndOfMessage)
        return $text.ToString()
    }
    catch { return $null }
    finally { $ws.Dispose(); $cts.Dispose() }
}

function Invoke-SmokeTest($project, [int]$Port, [string]$ExpectedCommit) {
    $base = "http://localhost:$Port"
    $failures = @()

    $landing = Get-Http "$base/" -Page
    if ($landing -and $landing.StatusCode -eq 200) { Ok 'Landing page HTTP 200' } else { $failures += "GET $base/ did not return 200" }

    $app = Get-Http "$base/app/comparative" -Page
    if ($app -and $app.StatusCode -eq 200) {
        # Production: the built /assets bundle. Development: the Vite client and
        # the app's entry module, compiled on request.
        $assets = @([regex]::Matches($app.Content, '(?:src|href)="(/(?:assets|src|@vite)/[^"]+)"') | ForEach-Object { $_.Groups[1].Value } | Select-Object -Unique)
        $bad = @($assets | Where-Object { $r = Get-Http "$base$_"; -not ($r -and $r.StatusCode -eq 200 -and $r.RawContentLength -gt 0) })
        $kind = if ($Dev) { 'modules compile and load' } else { 'static assets load' }
        if ($assets.Count -gt 0 -and $bad.Count -eq 0) { Ok "Dashboard HTTP 200, $($assets.Count) $kind" }
        else { $failures += "Dashboard assets failed to load: $($bad -join ', ')" }
    }
    else { $failures += "GET $base/app/comparative did not return 200" }

    try {
        $health = Invoke-RestMethod "$base/health" -TimeoutSec 10
        $via = if ($Dev) { 'the Vite dev server proxy' } else { 'nginx' }
        if ($health.status -eq 'healthy') { Ok "Backend /health healthy (through $via)" } else { $failures += "/health returned '$($health.status)'" }
    }
    catch { $failures += "/health unreachable: $($_.Exception.Message)" }

    try {
        $runs = Invoke-RestMethod "$base/api/v1/study/history/runs?limit=1" -TimeoutSec 10
        Ok "Database reachable through the API (history query returned $(@($runs).Count) row(s))"
    }
    catch { $failures += "Database query through the API failed: $($_.Exception.Message)" }

    if ($Dev) {
        # The development sign-in: the backend must accept the token the Vite
        # dev app sends (DEV_AUTH_BYPASS=1).
        try {
            $null = Invoke-RestMethod "$base/api/v1/replays?limit=1" -Headers @{ Authorization = 'Bearer urbanflow-local-dev' } -TimeoutSec 10
            Ok 'Development sign-in accepted (saving runs available)'
        }
        catch { $failures += "Development sign-in rejected: $($_.Exception.Message) (is DEV_AUTH_BYPASS set?)" }
    }

    # A one-seed, 2-second Monte Carlo study: exercises the study job API and
    # the worker process pool without writing anything to the database.
    try {
        $body = '{"numSeeds": 1, "duration": 2}'
        $job = Invoke-RestMethod "$base/api/v1/study/validate/monte-carlo/jobs" -Method Post -Body $body -ContentType 'application/json' -TimeoutSec 15
        $deadline = (Get-Date).AddSeconds(90)
        while ($job.status -notin @('completed', 'failed') -and (Get-Date) -lt $deadline) {
            Start-Sleep -Milliseconds 500
            $job = Invoke-RestMethod "$base/api/v1/study/jobs/$($job.jobId)" -TimeoutSec 10
        }
        if ($job.status -eq 'completed') { Ok "Study workers ran a job ($($job.progress.total) simulations)" }
        else { $failures += "Study job did not complete: status '$($job.status)' $($job.error)" }
    }
    catch { $failures += "Study job API failed: $($_.Exception.Message)" }

    $frame = Receive-WebSocketFrame "ws://localhost:$Port/ws/simulation/live"
    if ($frame -and $frame -match '"schemaVersion"') { Ok 'Live WebSocket stream delivers snapshots' }
    else { $failures += 'No snapshot received from ws://.../ws/simulation/live' }

    try {
        $version = Invoke-RestMethod "$base/api/version" -TimeoutSec 10
        if ($version.gitCommit -eq $ExpectedCommit) {
            $shown = if ($Dev) { 'live source, reported as unknown' } elseif ($ExpectedCommit -eq 'unknown') { 'uncommitted backend changes' } else { $ExpectedCommit.Substring(0, 12) }
            Ok "Backend reports the expected source version ($shown)"
        }
        else { $failures += "Backend reports commit '$($version.gitCommit)', expected '$ExpectedCommit' (rebuild with .\start.ps1)" }
    }
    catch { $failures += "/api/version unreachable: $($_.Exception.Message)" }

    $containers = Get-Containers
    foreach ($s in $Services) {
        $c = $containers[$s]
        $built = Get-ImageId (Get-ImageName $s)
        $running = Get-RunningImage $c
        if ($running -and $running -eq $built) { Ok "$s runs the current image ($(Short $built))" }
        else { $failures += "$s runs image $(Short $running), but the current build is $(Short $built) (run .\start.ps1)" }
    }

    if ($failures.Count -gt 0) { Fail 'Smoke test failed:' $failures }
}

# -- Modes ----------------------------------------------------------------

function Show-Ready($envInfo, $prov) {
    $port = $envInfo.HttpPort
    $url = if ($port -eq 80) { 'http://localhost' } else { "http://localhost:$port" }
    Write-Host ''
    Write-Host "UrbanFlow ready ($StackName)" -ForegroundColor Green
    Write-Host "Frontend: $url   (comparative: $url/app/comparative)"
    if ($Dev) {
        Write-Host 'Backend:  http://localhost:8000   (API docs: http://localhost:8000/docs; also proxied at /api)'
        Write-Host 'Reload:   edits under frontend/ and backend/src apply live; dependency changes need .\start.ps1 -Dev'
        Write-Host 'Sign-in:  development bypass (Local developer)'
    }
    else { Write-Host "Backend:  $url/api   (health: $url/health, version: $url/api/version)" }
    $commit = if ($prov.HasGit) { "$($prov.Commit.Substring(0, 12)) on $($prov.Branch)$(if ($prov.Dirty.Count) { ' + uncommitted changes' })" } else { 'unknown' }
    Write-Host "Commit:   $commit"
    Write-Host "Database: persistent Docker volume $(Get-VolumeName $envInfo.Model)"
    $flag = if ($Dev) { ' -Dev' } else { '' }
    Write-Host "Logs:     .\start.ps1$flag -Logs [backend|frontend]    Status: .\start.ps1$flag -Status"
    if (-not $NoBrowser) { Start-Process $url }
}

function Invoke-Up([switch]$NoCache, [switch]$RecreateOnly) {
    $started = Get-Date
    $script:StepTotal = 7
    Step 'Docker'
    Assert-Docker -AllowStart

    Step 'Environment'
    $envInfo = Test-Environment
    $project = $envInfo.Model.name
    $other = @((Get-Containers).Values | Where-Object { (Get-StackOf $_) -ne $StackName -and $_.State.Status -eq 'running' })
    if ($other.Count -gt 0) {
        Info "The $(Get-StackOf $other[0]) stack is running; it will be replaced by the $StackName stack (each keeps its own database volume)."
    }
    Test-Ports $envInfo.Ports

    Step 'Change detection'
    $prov = Get-Provenance
    Show-Provenance $prov
    $expected = Get-ExpectedBackendCommit $prov
    if ($Dev) {
        # The dev images hold dependencies only; the running code is whatever
        # is in the working tree, so no commit is claimed for it.
        $expected = 'unknown'
        Info 'Development: source is bind-mounted and reloads live; images rebuild only for dependency changes.'
    }
    else {
        # Build arg for backend/Dockerfile (see Get-ExpectedBackendCommit).
        $env:GIT_COMMIT = if ($expected -eq 'unknown') { '' } else { $expected }
        if ($expected -eq 'unknown' -and $prov.HasGit) { Info 'Backend has uncommitted changes: saved runs will record commit "unknown".' }
    }
    $volume = Get-VolumeName $envInfo.Model
    $volumeIsNew = -not (Test-VolumeExists $volume)

    Step 'Build'
    if ($RecreateOnly) {
        $missing = @($Services | Where-Object { -not (Get-ImageId (Get-ImageName $_)) })
        if ($missing.Count -gt 0) { Fail "No image for $($missing -join ', ') yet." @('Run .\start.ps1 first to build it.') }
        Info 'Skipped (-Restart reuses the current images)'
        $rebuilt = @()
    }
    else { $rebuilt = Invoke-Build $project -NoCache:$NoCache }

    Step 'Containers'
    Start-Containers -ForceRecreate:$RecreateOnly -RebuiltImages $rebuilt

    Step 'Health'
    Wait-Healthy
    Test-Database $envInfo.Model $volumeIsNew

    Step 'Smoke test'
    Invoke-SmokeTest $project $envInfo.HttpPort $expected
    Info ("Total: {0}s" -f [int]((Get-Date) - $started).TotalSeconds)
    Show-Ready $envInfo $prov
}

function Invoke-Status {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue) -or -not (Test-DockerDaemon)) {
        Warn 'Docker engine is not running; nothing is being served.'
        Show-Provenance (Get-Provenance)
        return
    }
    $model = Get-ComposeModel
    $project = $model.name
    $prov = Get-Provenance
    Write-Host "UrbanFlow status (project '$project')" -ForegroundColor Cyan
    Show-Provenance $prov
    Write-Host ''
    $containers = Get-Containers
    $up = @($containers.Values | Where-Object { $_.State.Status -eq 'running' })
    $sameStack = $true
    if ($up.Count -gt 0) {
        $stack = Get-StackOf $up[0]
        $hint = if ($Dev) { 'drop -Dev' } else { 'add -Dev' }
        $sameStack = $stack -eq $StackName
        $note = if (-not $sameStack) { "  (image and database details below are for the $StackName stack; $hint for the running one)" } else { '' }
        Info "Running stack: $stack$note"
    }
    foreach ($s in $Services) {
        $c = $containers[$s]
        $image = Get-ImageId (Get-ImageName $s)
        $state = Get-ContainerState $c
        $line = '  {0,-9} {1,-10}' -f $s, $state
        if ($c) {
            $since = ([datetime]$c.State.StartedAt).ToLocalTime().ToString('yyyy-MM-dd HH:mm')
            $running = Get-RunningImage $c
            $line += " started $since, image $(Short $running)"
            if ($sameStack -and $image -and $running -ne $image) { $line += '  (a newer image exists: run .\start.ps1)' }
        }
        elseif ($image) { $line += " image $(Short $image) built, no container" }
        else { $line += ' not built' }
        Write-Host $line
    }
    $labels = Invoke-Docker image inspect --format '{{json .Config.Labels}}' (Get-ImageName 'backend')
    if (-not $Dev -and $sameStack -and $LASTEXITCODE -eq 0) {
        $parsed = ($labels | Select-Object -First 1) | ConvertFrom-Json
        $label = if ($parsed -and $parsed.PSObject.Properties['org.opencontainers.image.revision']) { "$($parsed.'org.opencontainers.image.revision')".Trim() } else { '' }
        $expected = Get-ExpectedBackendCommit $prov
        $built = if ($label) { $label.Substring(0, 12) } else { 'uncommitted changes' }
        $current = if ($expected -eq 'unknown') { 'uncommitted changes' } else { $expected.Substring(0, 12) }
        $note = if (($label -and $label -eq $expected) -or (-not $label -and $expected -eq 'unknown')) { 'matches the current source' } else { "current source is $current; run .\start.ps1 to rebuild" }
        Info "Backend image built from: $built ($note)"
    }
    $volume = Get-VolumeName $model
    if (Test-VolumeExists $volume) {
        $info = if ($sameStack -and (Get-ContainerState $containers['backend']) -in @('healthy', 'starting')) { Get-DatabaseInfo } else { $null }
        if ($info) { Info ("Database: volume '{0}', {1} saved runs, {2} sweeps, {3:N1} MB" -f $volume, $info.runs, $info.sweeps, ($info.bytes / 1MB)) }
        else { Info "Database: volume '$volume' (its backend is not running)" }
    }
    else { Info "Database: volume '$volume' does not exist yet" }
    $ports = @($containers.Values | ForEach-Object { Get-PublishedPorts $_ } | Sort-Object -Unique)
    if ($ports.Count -gt 0) { Info "Serving: $(($ports | ForEach-Object { "http://localhost:$_" }) -join ', ')" }
}

function Invoke-Clean {
    $script:StepTotal = if ($DeleteData) { 3 } else { 2 }
    Step 'Docker'
    Assert-Docker
    $model = Get-ComposeModel
    $volume = Get-VolumeName $model
    Step 'Containers and images'
    # Development images carry explicit names (image: in the dev file), which
    # `--rmi local` would keep; every image either stack uses is built here.
    $rmi = if ($Dev) { 'all' } else { 'local' }
    $out = Invoke-Docker compose down --rmi $rmi --remove-orphans
    if ($LASTEXITCODE -ne 0) { Fail 'docker compose down failed:' ($out | Select-Object -Last 6) }
    # Both stacks share the Compose project, so this clears either one.
    Ok "Containers, network and built images removed (production and development share project '$($model.name)')"
    $kept = @(Invoke-Docker volume ls -q --filter "label=com.docker.compose.project=$($model.name)" | Where-Object { $_ -and ($_ -ne $volume -or -not $DeleteData) })
    foreach ($v in $kept) { Ok "Database volume '$v' kept" }
    if (-not $DeleteData) { return }
    Step 'Database volume'
    if (-not (Test-VolumeExists $volume)) { Ok "No database volume '$volume' to delete"; return }
    if (-not $Force) {
        Write-Host "  This permanently deletes every saved run and sweep in '$volume'." -ForegroundColor Yellow
        $answer = Read-Host "  Type the volume name to confirm"
        if ($answer -ne $volume) { Ok 'Not confirmed; database volume kept'; return }
    }
    $out = Invoke-Docker volume rm $volume
    if ($LASTEXITCODE -ne 0) { Fail "Could not delete '$volume':" ($out | Select-Object -Last 4) }
    Ok "Database volume '$volume' deleted"
}

# Build settings are set for docker in this process only; put the caller's
# values back afterwards (the script runs in the caller's session).
$savedEnv = @{}
foreach ($name in @('GIT_COMMIT', 'BUILDX_NO_DEFAULT_ATTESTATIONS')) { $savedEnv[$name] = [Environment]::GetEnvironmentVariable($name) }
try {
switch ($PSCmdlet.ParameterSetName) {
    'Status' { Invoke-Status }
    'Logs' {
        Assert-Docker
        $logArgs = Add-ComposeFile @('compose', 'logs', '-f', '--tail', '200')
        if ($Service) { $logArgs += $Service }
        & docker @logArgs
    }
    'SmokeTest' {
        $script:StepTotal = 2
        Step 'Docker'
        Assert-Docker
        $envInfo = Test-Environment
        $containers = Get-Containers
        foreach ($s in $Services) {
            $state = Get-ContainerState $containers[$s]
            if ($state -ne 'healthy') { Fail "$s is $state." @('Start the stack with .\start.ps1') }
        }
        Step 'Smoke test'
        $expected = if ($Dev) { 'unknown' } else { Get-ExpectedBackendCommit (Get-Provenance) }
        Invoke-SmokeTest $envInfo.Model.name $envInfo.HttpPort $expected
        Write-Host ''
        Write-Host 'Smoke test passed' -ForegroundColor Green
    }
    'Clean' { Invoke-Clean }
    'Restart' { Invoke-Up -RecreateOnly }
    'Rebuild' { Invoke-Up -NoCache }
    default { Invoke-Up }
}
}
finally {
    foreach ($name in $savedEnv.Keys) { [Environment]::SetEnvironmentVariable($name, $savedEnv[$name]) }
}
