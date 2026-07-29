param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
}

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
$ReposRoot = Join-Path $ProjectRoot "repos"
$DocsRoot = Join-Path $ProjectRoot "docs"
$ConfigsRoot = Join-Path $ProjectRoot "configs"
$ManifestsRoot = Join-Path $ProjectRoot "manifests"

function Write-TextFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Content,

        [switch]$Overwrite
    )

    if ((Test-Path -LiteralPath $Path) -and (-not $Overwrite)) {
        Write-Host "Skipped existing file: $Path"
        return
    }

    $Encoding = New-Object System.Text.UTF8Encoding -ArgumentList $false
    [System.IO.File]::WriteAllText($Path, $Content, $Encoding)
}

function Invoke-NativeGit {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"

    try {
        $Output = & git -C $WorkingDirectory @Arguments 2>&1
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $PreviousErrorActionPreference
    }

    return [pscustomobject]@{
        ExitCode = $ExitCode
        Output = ($Output -join "`n").Trim()
    }
}

Write-Host "=== Research repository initialization v2 ==="
Write-Host "Project root: $ProjectRoot"
Write-Host ""

if (-not (Test-Path -LiteralPath $ReposRoot -PathType Container)) {
    throw "repos directory was not found: $ReposRoot"
}

foreach ($Directory in @(
    (Join-Path $ProjectRoot "scripts"),
    (Join-Path $ProjectRoot "experiments"),
    (Join-Path $ProjectRoot "docker"),
    $DocsRoot,
    $ConfigsRoot,
    $ManifestsRoot
)) {
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
}

Write-Host "[1/8] Checking parent Git repository..."

$ParentGitPath = Join-Path $ProjectRoot ".git"

if (-not (Test-Path -LiteralPath $ParentGitPath)) {
    $InitResult = Invoke-NativeGit `
        -WorkingDirectory $ProjectRoot `
        -Arguments @("init")

    if ($InitResult.ExitCode -ne 0) {
        throw "Failed to initialize parent Git repository.`n$($InitResult.Output)"
    }

    $BranchResult = Invoke-NativeGit `
        -WorkingDirectory $ProjectRoot `
        -Arguments @("symbolic-ref", "HEAD", "refs/heads/main")

    if ($BranchResult.ExitCode -ne 0) {
        throw "Failed to set the main branch.`n$($BranchResult.Output)"
    }

    Write-Host "Initialized parent Git repository."
}
else {
    Write-Host "Parent Git repository already exists."
}

Write-Host "[2/8] Creating .gitignore..."

$GitIgnore = @'
# Secrets and local configuration
.env
.env.*
!.env.example
*.key
*.pem
*.p12
credentials.json
secrets.json

# External repositories
# These will be converted to Git submodules later.
/repos/

# Build outputs
**/build/
**/cmake-build-*/
**/out/
*.o
*.obj
*.exe
*.dll
*.so
*.dylib
*.a
*.lib

# Test coverage
.coverage/
coverage.info
*.gcda
*.gcno
*.gcov

# Cache
.cache/
__pycache__/
*.pyc
.pytest_cache/

# Temporary files
*.tmp
*.temp
*.bak
*~
*.swp

# Full source backups can be restored from fixed commits.
**/backup/ini.h.original

# Docker local data
docker-data/
volumes/

# Editors and operating systems
.vscode/
.idea/
.DS_Store
Thumbs.db
desktop.ini
'@

Write-TextFile `
    -Path (Join-Path $ProjectRoot ".gitignore") `
    -Content ($GitIgnore + "`n") `
    -Overwrite

Write-Host "[3/8] Creating .gitattributes..."

$GitAttributes = @'
* text=auto

*.ps1 text eol=crlf
*.sh text eol=lf
*.cpp text eol=lf
*.cc text eol=lf
*.c text eol=lf
*.h text eol=lf
*.hpp text eol=lf
*.py text eol=lf
*.json text eol=lf
*.csv text eol=lf
*.md text eol=lf
*.txt text eol=lf
*.log text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
'@

Write-TextFile `
    -Path (Join-Path $ProjectRoot ".gitattributes") `
    -Content ($GitAttributes + "`n") `
    -Overwrite

Write-Host "[4/8] Creating repository documentation..."

$Readme = @'
# C++ Design Document Round-Trip Dataset

C++ソースコードからLLMを用いて設計文書を生成し，
生成した設計文書からコードを再生成した上で，
既存のビルドおよびテストスイートによって正当性を評価する研究用リポジトリである。

## Repository contents

- `repos/`: 実験対象となる外部Gitリポジトリ
- `scripts/`: 対象抽出，生成，置換，評価，復元用スクリプト
- `experiments/`: LLM入力，プロンプト，生成結果，ログ，判定結果
- `docker/`: 固定実験環境
- `configs/`: モデルおよび実験条件
- `manifests/`: リポジトリ，対象，実験実行の一覧
- `docs/`: 実験手順および運用規則

## Current minimal experiment

- Repository: `SSARCandy/ini-cpp`
- Target: `INIWriter::write`
- Regeneration scope: function body
- Evaluation: build, direct tests and full tests
- Automatic repair: disabled
- Retry: disabled

## Reproducibility policy

各実験では，対象リポジトリのコミット，LLM入力，プロンプト，
未加工出力，評価対象コード，ビルドログ，テストログ，SHA-256，
および最終判定を保存する。
'@

Write-TextFile `
    -Path (Join-Path $ProjectRoot "README.md") `
    -Content ($Readme + "`n") `
    -Overwrite

$RepositoryPolicy = @'
# Research Repository Policy

## 1. 外部リポジトリ

実験対象の外部リポジトリは，特定のコミットに固定する。
最終的にはGit submoduleとして管理する。
元リポジトリのソースコードを研究用親リポジトリへ直接コピーしない。

## 2. 実験単位

各実験実行には一意のrun IDを付与する。
過去の実験結果は上書きしない。

## 3. 保存するデータ

- LLMへ実際に送信した入力
- プロンプト
- LLMの未加工応答
- 整形後の設計文書
- 再生成コード
- ビルドログ
- 直接テストログ
- 全テストログ
- 復元ログ
- メタデータ
- 最終判定

## 4. 保存しないデータ

- APIキー
- パスワード
- `.env`
- ビルド生成物
- Dockerイメージ
- モデル重み
- キャッシュ

## 5. LLM出力

LLMの未加工応答と，実際に評価したコードを別ファイルで保存する。
人間が修正した場合は，修正内容を必ず記録する。
最小実験では生成コードに対する修正を行わない。

## 6. 実験失敗

コンパイル失敗，テスト失敗，タイムアウトなども研究データとして保存する。
成功結果だけを選択して残してはならない。
'@

Write-TextFile `
    -Path (Join-Path $DocsRoot "repository_policy.md") `
    -Content ($RepositoryPolicy + "`n") `
    -Overwrite

Write-Host "[5/8] Creating configuration templates..."

$EnvExample = @'
LLM_PROVIDER=
LLM_MODEL_ID=
LLM_API_KEY=
'@

Write-TextFile `
    -Path (Join-Path $ProjectRoot ".env.example") `
    -Content ($EnvExample + "`n") `
    -Overwrite

$ModelExample = @'
{
  "provider": "",
  "model_id": "",
  "temperature": 0,
  "seed": null,
  "max_output_tokens": null,
  "retry_count": 0,
  "automatic_repair": false
}
'@

Write-TextFile `
    -Path (Join-Path $ConfigsRoot "model.example.json") `
    -Content ($ModelExample + "`n") `
    -Overwrite

Write-Host "[6/8] Inspecting external repositories..."

$RepositoryRecords = @()

$RepositoryDirectories = @(
    Get-ChildItem -LiteralPath $ReposRoot -Directory -Force |
    Sort-Object Name
)

foreach ($RepositoryDirectory in $RepositoryDirectories) {
    $NestedGitPath = Join-Path $RepositoryDirectory.FullName ".git"

    if (-not (Test-Path -LiteralPath $NestedGitPath)) {
        $RepositoryRecords += [pscustomobject]@{
            repository_id = $RepositoryDirectory.Name
            local_path = "repos/$($RepositoryDirectory.Name)"
            origin_url = ""
            commit = ""
            current_management = "not_a_git_repository"
            planned_management = "manual_review"
            captured_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
        }
        continue
    }

    $CommitResult = Invoke-NativeGit `
        -WorkingDirectory $RepositoryDirectory.FullName `
        -Arguments @("rev-parse", "HEAD")

    $OriginResult = Invoke-NativeGit `
        -WorkingDirectory $RepositoryDirectory.FullName `
        -Arguments @("config", "--get", "remote.origin.url")

    $RepositoryRecords += [pscustomobject]@{
        repository_id = $RepositoryDirectory.Name
        local_path = "repos/$($RepositoryDirectory.Name)"
        origin_url = $(if ($OriginResult.ExitCode -eq 0) { $OriginResult.Output } else { "" })
        commit = $(if ($CommitResult.ExitCode -eq 0) { $CommitResult.Output } else { "" })
        current_management = "existing_clone"
        planned_management = "git_submodule"
        captured_at_utc = [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    }
}

$RepositoriesManifestPath = Join-Path $ManifestsRoot "repositories.csv"

$RepositoryRecords |
    Export-Csv `
        -LiteralPath $RepositoriesManifestPath `
        -NoTypeInformation `
        -Encoding UTF8

Write-Host "[7/8] Creating experiment manifests..."

$TargetsManifestPath = Join-Path $ManifestsRoot "targets.csv"

if (-not (Test-Path -LiteralPath $TargetsManifestPath)) {
    Write-TextFile `
        -Path $TargetsManifestPath `
        -Content "repository_id,target_id,target_name,target_granularity,source_file,status,notes`n"
}

$RunsManifestPath = Join-Path $ManifestsRoot "runs.csv"

if (-not (Test-Path -LiteralPath $RunsManifestPath)) {
    Write-TextFile `
        -Path $RunsManifestPath `
        -Content "run_id,repository_id,target_id,model_id,status,started_at_utc,completed_at_utc,result_path`n"
}

Write-Host "[8/8] Inspecting parent repository status..."

$StatusResult = Invoke-NativeGit `
    -WorkingDirectory $ProjectRoot `
    -Arguments @("status", "--short")

if ($StatusResult.ExitCode -ne 0) {
    throw "Failed to inspect parent Git status.`n$($StatusResult.Output)"
}

Write-Host ""
Write-Host "Initialization completed."
Write-Host ""
Write-Host "Detected external repositories:"
Write-Host "  $RepositoriesManifestPath"
Write-Host ""
Write-Host "Parent Git status:"
Write-Host ""

if ([string]::IsNullOrWhiteSpace($StatusResult.Output)) {
    Write-Host "(clean)"
}
else {
    Write-Host $StatusResult.Output
}

Write-Host ""
Write-Host "No commit was created."
Write-Host "No GitHub remote was configured."
Write-Host "repos/ is intentionally ignored until submodule conversion."
