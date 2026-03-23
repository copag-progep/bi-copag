param(
    [Parameter(Mandatory = $true)]
    [string]$Repo,

    [Parameter(Mandatory = $true)]
    [string]$Token,

    [string]$Branch = "",

    [string]$CommitMessage = "chore: publish SEI BI app"
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$allowedPaths = @(
    "backend",
    "frontend",
    "scripts",
    ".dockerignore",
    ".env.example",
    ".gitignore",
    "DEPLOY-MINIMO.md",
    "Dockerfile",
    "README.md",
    "package.json",
    "render.yaml",
    "requirements.txt",
    "vercel.json"
)

function Get-ContentSha {
    param(
        [string]$OwnerRepo,
        [string]$FilePath,
        [string]$BranchName,
        [hashtable]$Headers
    )

    $uri = "https://api.github.com/repos/$OwnerRepo/contents/$FilePath"
    if ($BranchName) {
        $uri = "$uri?ref=$BranchName"
    }

    try {
        $response = Invoke-RestMethod -Method Get -Uri $uri -Headers $Headers
        return $response.sha
    } catch {
        $statusCode = $_.Exception.Response.StatusCode.value__
        if ($statusCode -eq 404) {
            return $null
        }
        throw
    }
}

function Get-RelativeProjectPath {
    param(
        [string]$Root,
        [string]$FullPath
    )

    $rootWithSeparator = $Root
    if (-not $rootWithSeparator.EndsWith([System.IO.Path]::DirectorySeparatorChar)) {
        $rootWithSeparator += [System.IO.Path]::DirectorySeparatorChar
    }

    $rootUri = New-Object System.Uri($rootWithSeparator)
    $fileUri = New-Object System.Uri($FullPath)
    return $rootUri.MakeRelativeUri($fileUri).ToString().Replace("\", "/")
}

function Get-ProjectFiles {
    param([string]$Root)

    $files = New-Object System.Collections.Generic.List[System.String]
    foreach ($entry in $allowedPaths) {
        $fullPath = Join-Path $Root $entry
        if (-not (Test-Path $fullPath)) {
            continue
        }

        $item = Get-Item $fullPath
        if ($item.PSIsContainer) {
            Get-ChildItem $fullPath -Recurse -File | ForEach-Object {
                $relativePath = Get-RelativeProjectPath -Root $Root -FullPath $_.FullName
                if ($relativePath -notmatch "^frontend/node_modules/" -and
                    $relativePath -notmatch "^frontend/dist/" -and
                    $relativePath -notmatch "^backend/data/" -and
                    $relativePath -notmatch "^\.git/" -and
                    $relativePath -notmatch "^SEI/" -and
                    $relativePath -notmatch "^ListaProcessos_SEIPro_") {
                    $files.Add($relativePath)
                }
            }
        } else {
            $relativePath = Get-RelativeProjectPath -Root $Root -FullPath $item.FullName
            $files.Add($relativePath)
        }
    }

    return $files | Sort-Object -Unique
}

$headers = @{
    Authorization          = "Bearer $Token"
    Accept                 = "application/vnd.github+json"
    "User-Agent"           = "codex-sei-bi-publisher"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$files = Get-ProjectFiles -Root $projectRoot
if (-not $files.Count) {
    throw "Nenhum arquivo elegivel foi encontrado para publicacao."
}

Write-Host "Publicando $($files.Count) arquivos em $Repo ..."

foreach ($relativePath in $files) {
    $absolutePath = Join-Path $projectRoot $relativePath
    $bytes = [System.IO.File]::ReadAllBytes($absolutePath)
    $contentBase64 = [Convert]::ToBase64String($bytes)
    $sha = Get-ContentSha -OwnerRepo $Repo -FilePath $relativePath -BranchName $Branch -Headers $headers

    $body = @{
        message = $CommitMessage
        content = $contentBase64
    }

    if ($sha) {
        $body.sha = $sha
    }

    if ($Branch) {
        $body.branch = $Branch
    }

    $jsonBody = $body | ConvertTo-Json -Depth 5
    $uri = "https://api.github.com/repos/$Repo/contents/$relativePath"
    Invoke-RestMethod -Method Put -Uri $uri -Headers $headers -Body $jsonBody
    Write-Host "OK $relativePath"
}

Write-Host "Publicacao concluida em https://github.com/$Repo"
