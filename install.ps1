#
# Vishwa Autocomplete Installer for Windows
# One command to install everything needed for the VS Code extension
#
# Usage:
#   iwr -useb https://raw.githubusercontent.com/YOUR_REPO/vishwa/main/install.ps1 | iex
#   or
#   .\install.ps1
#

$ErrorActionPreference = "Stop"

function Write-Step { param($Message) Write-Host "==> " -ForegroundColor Blue -NoNewline; Write-Host $Message }
function Write-Success { param($Message) Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $Message }
function Write-Warning { param($Message) Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }
function Write-Error { param($Message) Write-Host "[ERROR] " -ForegroundColor Red -NoNewline; Write-Host $Message }

Write-Host ""
Write-Host "========================================"
Write-Host "   Vishwa Autocomplete Installer"
Write-Host "========================================"
Write-Host ""

# Find Python
Write-Step "Looking for Python 3..."

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $version = & $cmd --version 2>&1
        if ($version -match "Python 3") {
            $pythonCmd = $cmd
            break
        }
    } catch {
        continue
    }
}

if (-not $pythonCmd) {
    Write-Error "Python 3 not found. Please install Python 3.8+ first."
    Write-Host ""
    Write-Host "Download from: https://www.python.org/downloads/"
    Write-Host "Make sure to check 'Add Python to PATH' during installation."
    exit 1
}

$pythonVersion = & $pythonCmd --version 2>&1
Write-Success "Found $pythonVersion ($pythonCmd)"

# Set up directories
$vishwaDir = Join-Path $env:USERPROFILE ".vishwa"
$venvDir = Join-Path $vishwaDir "venv"

Write-Step "Setting up Vishwa directory at $vishwaDir..."

# Create directory
if (-not (Test-Path $vishwaDir)) {
    New-Item -ItemType Directory -Path $vishwaDir -Force | Out-Null
}

# Check if venv already exists
if (Test-Path $venvDir) {
    Write-Warning "Virtual environment already exists at $venvDir"
    $response = Read-Host "Do you want to recreate it? (y/N)"
    if ($response -eq "y" -or $response -eq "Y") {
        Remove-Item -Recurse -Force $venvDir
    } else {
        Write-Step "Using existing virtual environment..."
    }
}

# Create virtual environment if it doesn't exist
if (-not (Test-Path $venvDir)) {
    Write-Step "Creating virtual environment..."
    & $pythonCmd -m venv $venvDir
    Write-Success "Virtual environment created"
}

# Determine pip and python paths
$pip = Join-Path $venvDir "Scripts\pip.exe"
$pythonVenv = Join-Path $venvDir "Scripts\python.exe"

# Upgrade pip
Write-Step "Upgrading pip..."
& $pip install --upgrade pip -q

# Install vishwa
Write-Step "Installing Vishwa..."

# Check if we're in the vishwa source directory (for development)
if ((Test-Path "pyproject.toml") -and (Select-String -Path "pyproject.toml" -Pattern "name.*vishwa" -Quiet)) {
    Write-Step "Installing from local source..."
    & $pip install -e . -q
} else {
    # Install from GitHub or PyPI
    Write-Step "Installing from GitHub..."
    try {
        & $pip install git+https://github.com/SrujanArjun/Vishwa.git -q 2>$null
    } catch {
        Write-Warning "Failed to install from GitHub. Trying PyPI..."
        try {
            & $pip install vishwa -q
        } catch {
            Write-Error "Vishwa package not found. Please install manually."
            exit 1
        }
    }
}

Write-Success "Vishwa installed successfully"

# Verify installation
Write-Step "Verifying installation..."
try {
    & $pythonVenv -c "import vishwa.autocomplete.service" 2>$null
    Write-Success "Vishwa autocomplete service is ready"
} catch {
    Write-Error "Installation verification failed"
    exit 1
}

# Create .env template if it doesn't exist
$envFile = Join-Path $vishwaDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Step "Creating configuration template..."
    @"
# Vishwa Configuration
# Uncomment and set the model you want to use

# For local models (Ollama)
VISHWA_MODEL=gemma3:4b

# For cloud models (uncomment one)
# VISHWA_MODEL=claude-haiku-4-5
# ANTHROPIC_API_KEY=your-api-key-here

# VISHWA_MODEL=gpt-4o-mini
# OPENAI_API_KEY=your-api-key-here
"@ | Out-File -FilePath $envFile -Encoding utf8
    Write-Success "Configuration template created at $envFile"
}

Write-Host ""
Write-Host "========================================"
Write-Host "   Installation Complete"
Write-Host "========================================"
Write-Host ""
Write-Host "Next steps:"
Write-Host ""
Write-Host "  1. Install the VS Code extension:"
Write-Host "     - Open VS Code"
Write-Host "     - Go to Extensions (Ctrl+Shift+X)"
Write-Host "     - Search for 'Vishwa Autocomplete'"
Write-Host "     - Click Install"
Write-Host ""
Write-Host "  2. Configure your model (optional):"
Write-Host "     Edit $envFile"
Write-Host ""
Write-Host "  3. For local models, install Ollama:"
Write-Host "     https://ollama.ai"
Write-Host "     Then run: ollama pull gemma3:4b"
Write-Host ""
Write-Warning "If autocomplete doesn't work in other projects:"
Write-Host "  Check VS Code settings - ensure 'vishwa.autocomplete.pythonPath'"
Write-Host "  is set to 'auto' (recommended) or: $pythonVenv"
Write-Host ""
