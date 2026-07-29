param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = (
        Resolve-Path (Join-Path $PSScriptRoot "..\..")
    ).Path
}

$ExpectedCommit =
    "e1779b837274de8be2051bef579c3b9ec3483522"

$ExpectedSubmoduleCommit =
    "391ce627def20c1e8a54d10b12949b15086473dd"

$RepositoryRoot = Join-Path $ProjectRoot "repos\ini-cpp"
$SubmoduleRoot = Join-Path $RepositoryRoot "googletest"
$SourcePath = Join-Path $RepositoryRoot "ini\ini.h"

$ExperimentRoot = Join-Path `
    $ProjectRoot `
    "experiments\ini-writer-minimal"

$InputDirectory = Join-Path $ExperimentRoot "input"
$BackupDirectory = Join-Path $ExperimentRoot "backup"
$LogDirectory = Join-Path $ExperimentRoot "logs"
$ResultDirectory = Join-Path $ExperimentRoot "result"

$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Content
    )

    [System.IO.File]::WriteAllText(
        $Path,
        $Content,
        $Utf8NoBom
    )
}

function Invoke-RepoGit {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $Output = & git -C $RepositoryRoot @Arguments 2>&1
    $ExitCode = $LASTEXITCODE

    if ($ExitCode -ne 0) {
        throw @"
Git command failed.

Command:
git -C "$RepositoryRoot" $($Arguments -join " ")

Output:
$($Output -join "`n")
"@
    }

    return ($Output -join "`n").Trim()
}

function Get-LineNumber {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,

        [Parameter(Mandatory = $true)]
        [int]$Index
    )

    if ($Index -le 0) {
        return 1
    }

    return (
        [regex]::Matches(
            $Text.Substring(0, $Index),
            "`n"
        )
    ).Count + 1
}

Write-Host "=== Step 1: Prepare INIWriter experiment ==="

if (-not (Test-Path -LiteralPath $RepositoryRoot -PathType Container)) {
    throw "Repository not found: $RepositoryRoot"
}

if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) {
    throw "Source file not found: $SourcePath"
}

if (-not (Test-Path -LiteralPath $SubmoduleRoot -PathType Container)) {
    throw "GoogleTest submodule not found: $SubmoduleRoot"
}

foreach ($Directory in @(
    $ExperimentRoot,
    $InputDirectory,
    $BackupDirectory,
    $LogDirectory,
    $ResultDirectory
)) {
    New-Item `
        -ItemType Directory `
        -Force `
        -Path $Directory |
    Out-Null
}

Write-Host "[1/8] Checking repository commit..."

$RepositoryCommit = Invoke-RepoGit -Arguments @(
    "rev-parse",
    "HEAD"
)

if ($RepositoryCommit -ne $ExpectedCommit) {
    throw @"
Repository commit mismatch.

Expected:
$ExpectedCommit

Actual:
$RepositoryCommit
"@
}

Write-Host "[2/8] Checking GoogleTest submodule..."

$SubmoduleOutput =
    & git -C $SubmoduleRoot rev-parse HEAD 2>&1

$SubmoduleExitCode = $LASTEXITCODE
$SubmoduleCommit = ($SubmoduleOutput -join "`n").Trim()

if ($SubmoduleExitCode -ne 0) {
    throw "Failed to read GoogleTest submodule commit."
}

if ($SubmoduleCommit -ne $ExpectedSubmoduleCommit) {
    throw @"
GoogleTest submodule commit mismatch.

Expected:
$ExpectedSubmoduleCommit

Actual:
$SubmoduleCommit
"@
}

Write-Host "[3/8] Checking tracked changes..."

$RepositoryStatus = Invoke-RepoGit -Arguments @(
    "status",
    "--short",
    "--untracked-files=no"
)

if (-not [string]::IsNullOrWhiteSpace($RepositoryStatus)) {
    throw "Tracked changes exist in ini-cpp:`n$RepositoryStatus"
}

$SubmoduleStatusOutput =
    & git -C $SubmoduleRoot status --short 2>&1

$SubmoduleStatusExitCode = $LASTEXITCODE
$SubmoduleStatus = ($SubmoduleStatusOutput -join "`n").Trim()

if ($SubmoduleStatusExitCode -ne 0) {
    throw "Failed to inspect the GoogleTest submodule."
}

if (-not [string]::IsNullOrWhiteSpace($SubmoduleStatus)) {
    throw "Changes exist in GoogleTest:`n$SubmoduleStatus"
}

Write-Host "[4/8] Reading ini/ini.h..."

$SourceBytes = [System.IO.File]::ReadAllBytes($SourcePath)
$SourceText = [System.IO.File]::ReadAllText($SourcePath)
$SourceHash = (
    Get-FileHash `
        -LiteralPath $SourcePath `
        -Algorithm SHA256
).Hash.ToLowerInvariant()

Write-Host "[5/8] Locating INIWriter and its leading comment..."

$ClassMarker = "class INIWriter {"

$ClassStart = $SourceText.IndexOf(
    $ClassMarker,
    [System.StringComparison]::Ordinal
)

if ($ClassStart -lt 0) {
    throw "class INIWriter was not found."
}

$SecondClassStart = $SourceText.IndexOf(
    $ClassMarker,
    $ClassStart + $ClassMarker.Length,
    [System.StringComparison]::Ordinal
)

if ($SecondClassStart -ge 0) {
    throw "Multiple INIWriter classes were found."
}

$TextBeforeClass = $SourceText.Substring(0, $ClassStart)

$CommentEnd = $TextBeforeClass.LastIndexOf(
    "*/",
    [System.StringComparison]::Ordinal
)

if ($CommentEnd -lt 0) {
    throw "The leading comment for INIWriter was not found."
}

$CommentStart = $TextBeforeClass.LastIndexOf(
    "/**",
    $CommentEnd,
    [System.StringComparison]::Ordinal
)

if ($CommentStart -lt 0) {
    throw "The start of the leading Doxygen comment was not found."
}

$BetweenCommentAndClass = $SourceText.Substring(
    $CommentEnd + 2,
    $ClassStart - ($CommentEnd + 2)
)

if (-not [string]::IsNullOrWhiteSpace($BetweenCommentAndClass)) {
    throw "Non-whitespace text exists between the leading comment and INIWriter."
}

$TextFromClass = $SourceText.Substring($ClassStart)

$ClassEndMatch = [regex]::Match(
    $TextFromClass,
    '(?m)^};'
)

if (-not $ClassEndMatch.Success) {
    throw "The end of INIWriter was not found."
}

$ClassEndExclusive =
    $ClassStart +
    $ClassEndMatch.Index +
    $ClassEndMatch.Length

$ClassText = $SourceText.Substring(
    $ClassStart,
    $ClassEndExclusive - $ClassStart
)

$DesignInput = $SourceText.Substring(
    $CommentStart,
    $ClassEndExclusive - $CommentStart
).TrimEnd() + "`n"

Write-Host "[6/8] Locating only the write() function body..."

$WriteMarker = "inline static void write"

$WriteStartInClass = $ClassText.IndexOf(
    $WriteMarker,
    [System.StringComparison]::Ordinal
)

if ($WriteStartInClass -lt 0) {
    throw "INIWriter::write was not found."
}

$OpenBraceInClass = $ClassText.IndexOf(
    "{",
    $WriteStartInClass,
    [System.StringComparison]::Ordinal
)

if ($OpenBraceInClass -lt 0) {
    throw "The opening brace of INIWriter::write was not found."
}

$BraceDepth = 0
$CloseBraceInClass = -1

:BraceScan
for (
    $Index = $OpenBraceInClass;
    $Index -lt $ClassText.Length;
    $Index++
) {
    $Character = $ClassText[$Index]

    if ($Character -eq "{") {
        $BraceDepth++
    }
    elseif ($Character -eq "}") {
        $BraceDepth--

        if ($BraceDepth -eq 0) {
            $CloseBraceInClass = $Index
            break BraceScan
        }
    }
}

if ($CloseBraceInClass -lt 0) {
    throw "The closing brace of INIWriter::write was not found."
}

$WriteOpenAbsolute = $ClassStart + $OpenBraceInClass
$WriteCloseAbsolute = $ClassStart + $CloseBraceInClass

$OriginalBody = $SourceText.Substring(
    $WriteOpenAbsolute + 1,
    $WriteCloseAbsolute - $WriteOpenAbsolute - 1
)

$BodyStartInDesignInput =
    ($WriteOpenAbsolute + 1) - $CommentStart

$BodyLength =
    $WriteCloseAbsolute -
    $WriteOpenAbsolute -
    1

$PlaceholderBody = @"

        /* REGENERATED_BODY */
    
"@

$FixedScaffold = $DesignInput.Remove(
    $BodyStartInDesignInput,
    $BodyLength
).Insert(
    $BodyStartInDesignInput,
    $PlaceholderBody
)

$DependencyMatches = [regex]::Matches(
    $OriginalBody,
    'reader\.(?<method>[A-Za-z_][A-Za-z0-9_]*)\s*\('
)

$DependencyMethods = @(
    $DependencyMatches |
        ForEach-Object {
            $_.Groups["method"].Value
        } |
        Sort-Object -Unique
)

$ExpectedDependencies = @(
    "Get",
    "Keys",
    "Sections"
)

foreach ($ExpectedDependency in $ExpectedDependencies) {
    if ($DependencyMethods -notcontains $ExpectedDependency) {
        throw "Expected dependency was not found: $ExpectedDependency"
    }
}

$InputStartLine = Get-LineNumber `
    -Text $SourceText `
    -Index $CommentStart

$ClassStartLine = Get-LineNumber `
    -Text $SourceText `
    -Index $ClassStart

$ClassEndLine = Get-LineNumber `
    -Text $SourceText `
    -Index ($ClassEndExclusive - 1)

$WriteOpenLine = Get-LineNumber `
    -Text $SourceText `
    -Index $WriteOpenAbsolute

$WriteCloseLine = Get-LineNumber `
    -Text $SourceText `
    -Index $WriteCloseAbsolute

Write-Host "[7/8] Writing experiment files..."

$DesignInputPath =
    Join-Path $InputDirectory "design_input.cpp"

$FixedScaffoldPath =
    Join-Path $InputDirectory "fixed_scaffold.cpp"

$OriginalBodyPath =
    Join-Path $BackupDirectory "original_write_body.cpp"

$DependencyContextPath =
    Join-Path $InputDirectory "dependency_context.txt"

$MetadataPath =
    Join-Path $InputDirectory "source_metadata.json"

$BackupSourcePath =
    Join-Path $BackupDirectory "ini.h.original"

$OriginalHashPath =
    Join-Path $BackupDirectory "original_sha256.txt"

$SummaryPath =
    Join-Path $LogDirectory "step1_summary.txt"

Write-Utf8File `
    -Path $DesignInputPath `
    -Content $DesignInput

Write-Utf8File `
    -Path $FixedScaffoldPath `
    -Content $FixedScaffold

Write-Utf8File `
    -Path $OriginalBodyPath `
    -Content $OriginalBody

$DependencyContext = @"
Target:
INIWriter::write

Namespace:
inih

Regeneration scope:
Only the contents inside the braces of INIWriter::write.

Fixed and not regenerated:
- The leading INIWriter comment
- The INIWriter class declaration
- The INIWriter default constructor
- The write() documentation comment
- The write() function name
- The write() return type
- The write() parameters
- inline and static qualifiers
- The inih namespace
- Include directives
- INIReader
- Tests
- CMake files

Available INIReader operations:
- INIReader::Sections()
- INIReader::Keys(section)
- INIReader::Get(section, key)
"@

Write-Utf8File `
    -Path $DependencyContextPath `
    -Content ($DependencyContext.Trim() + "`n")

[System.IO.File]::WriteAllBytes(
    $BackupSourcePath,
    $SourceBytes
)

Write-Utf8File `
    -Path $OriginalHashPath `
    -Content ($SourceHash + "`n")

$DesignInputHash = (
    Get-FileHash `
        -LiteralPath $DesignInputPath `
        -Algorithm SHA256
).Hash.ToLowerInvariant()

$Metadata = [ordered]@{
    repository = "SSARCandy/ini-cpp"
    repository_commit = $RepositoryCommit
    submodule_commit = $SubmoduleCommit

    target_class = "INIWriter"
    target_function = "INIWriter::write"
    target_granularity = "function_body"

    source_file = "ini/ini.h"
    source_sha256 = $SourceHash
    design_input_sha256 = $DesignInputHash

    design_input_start_line = $InputStartLine
    class_start_line = $ClassStartLine
    class_end_line = $ClassEndLine
    write_open_brace_line = $WriteOpenLine
    write_close_brace_line = $WriteCloseLine

    leading_class_comment_included = $true
    function_comment_included = $true
    original_function_body_included_for_design_generation = $true
    original_function_body_excluded_from_regeneration_input = $true

    replacement_scope = "INIWriter::write function body only"

    dependency_methods = $DependencyMethods

    generated_at_utc =
        [DateTime]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
}

Write-Utf8File `
    -Path $MetadataPath `
    -Content (
        ($Metadata | ConvertTo-Json -Depth 5) + "`n"
    )

$Summary = @"
Step 1 completed successfully.

Repository:
SSARCandy/ini-cpp

Repository commit:
$RepositoryCommit

Target class:
INIWriter

Target function:
INIWriter::write

Design-generation input:
Leading class comment + complete INIWriter class

Regeneration target:
Only the write() function body

Fixed during replacement:
Comments, class declaration, constructor, function signature,
namespace, includes, INIReader, tests and build configuration

Design input line range:
$InputStartLine-$ClassEndLine

Class line range:
$ClassStartLine-$ClassEndLine

write() brace lines:
$WriteOpenLine-$WriteCloseLine

Dependencies:
$($DependencyMethods -join ", ")

Source SHA-256:
$SourceHash

Design input SHA-256:
$DesignInputHash

Original source modified:
no
"@

Write-Utf8File `
    -Path $SummaryPath `
    -Content ($Summary.Trim() + "`n")

Write-Host "[8/8] Final verification..."

$FinalStatus = Invoke-RepoGit -Arguments @(
    "status",
    "--short",
    "--untracked-files=no"
)

if (-not [string]::IsNullOrWhiteSpace($FinalStatus)) {
    throw "The source repository changed unexpectedly:`n$FinalStatus"
}

Write-Host ""
Write-Host "Step 1 completed."
Write-Host ""
Write-Host "Design input:"
Write-Host "  $DesignInputPath"
Write-Host ""
Write-Host "Fixed scaffold:"
Write-Host "  $FixedScaffoldPath"
Write-Host ""
Write-Host "Original write body:"
Write-Host "  $OriginalBodyPath"
Write-Host ""
Write-Host "Metadata:"
Write-Host "  $MetadataPath"
Write-Host ""
Write-Host "Summary:"
Write-Host "  $SummaryPath"
