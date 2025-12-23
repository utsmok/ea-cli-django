# Claude Code Status Line Script
# Reads JSON input from stdin and outputs a formatted status line
# Styled to match Oh My Posh jandedobbeleer theme

$ErrorActionPreference = "SilentlyContinue"

$input = [Console]::In.ReadToEnd()
$data = $input | ConvertFrom-Json

# Extract relevant information
$modelName = $data.model.display_name
$currentDir = $data.workspace.current_dir
$projectDir = $data.workspace.project_dir
$outputStyle = $data.output_style.name

# Calculate context window usage
$usage = $data.context_window.current_usage
if ($usage -ne $null) {
    $inputTokens = $usage.input_tokens
    $cacheCreateTokens = $usage.cache_creation_input_tokens
    $cacheReadTokens = $usage.cache_read_input_tokens
    $currentTotal = $inputTokens + $cacheCreateTokens + $cacheReadTokens
    $contextSize = $data.context_window.context_window_size
    $usagePercent = [math]::Round(($currentTotal / $contextSize) * 100)
    $contextInfo = "$usagePercent%"
} else {
    $usagePercent = 0
    $contextInfo = "0%"
}

# Get git branch
$branch = ""
$gitStatus = ""
if (Test-Path .git) {
    $branch = git -c core.fsmonitor=false rev-parse --abbrev-ref HEAD 2>$null
    if ($branch) {
        # Check for changes
        $status = git -c core.fsmonitor=false status --porcelain 2>$null
        if ($status) {
            $gitStatus = "*"
        }
    }
}

# Get current directory name (abbreviated like Oh My Posh)
$dirName = Split-Path -Leaf $currentDir

# Get timestamp
$time = Get-Date -Format "HH:mm:ss"

# Oh My Posh style: uses segments with background/foreground colors
# Since we're limited in Claude Code, we'll approximate with separators

# Build the status line segments
# Segment 1: Time (grey background, white text - approximated)
$segments = @()
$segments += "$time"

# Segment 2: Model (blue - approximated)
$modelShort = $modelName -replace "Claude ", "" -replace " Sonnet", ""
$segments += $modelShort

# Segment 3: Directory (yellow)
$segments += $dirName

# Segment 4: Git branch (green with status indicator)
if ($branch) {
    $gitSegment = $branch
    if ($gitStatus) {
        $gitSegment = "$gitSegment$gitStatus"
    }
    $segments += $gitSegment
}

# Segment 5: Context (color-coded by usage)
if ($usagePercent -gt 80) {
    $segments += $contextInfo
} elseif ($usagePercent -gt 50) {
    $segments += $contextInfo
} else {
    $segments += $contextInfo
}

# Output with Oh My Posh style separators
$separator = " "
$output = $segments -join $separator

# Write colored output
Write-Host -NoNewline "$time "
Write-Host -NoNewline -ForegroundColor Cyan "$modelShort "
Write-Host -NoNewline -ForegroundColor Yellow "$dirName "

if ($branch) {
    if ($gitStatus) {
        Write-Host -NoNewline -ForegroundColor Magenta "$branch$gitStatus "
    } else {
        Write-Host -NoNewline -ForegroundColor Green "$branch "
    }
}

if ($usagePercent -gt 80) {
    Write-Host -NoNewline -ForegroundColor Red "$contextInfo"
} elseif ($usagePercent -gt 50) {
    Write-Host -NoNewline -ForegroundColor Yellow "$contextInfo"
} else {
    Write-Host -NoNewline -ForegroundColor Green "$contextInfo"
}
