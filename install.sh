#!/bin/bash
#
# Vishwa Autocomplete Installer
# One command to install everything needed for the VS Code extension
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/YOUR_REPO/vishwa/main/install.sh | bash
#   or
#   ./install.sh
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_step() {
    echo -e "${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     OS="linux";;
        Darwin*)    OS="macos";;
        MINGW*|MSYS*|CYGWIN*) OS="windows";;
        *)          OS="unknown";;
    esac
    echo $OS
}

# Find Python 3
find_python() {
    # Try common Python commands
    for cmd in python3 python py; do
        if command -v "$cmd" &> /dev/null; then
            # Verify it's Python 3
            version=$("$cmd" --version 2>&1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
            major=$(echo "$version" | cut -d. -f1)
            if [ "$major" = "3" ]; then
                echo "$cmd"
                return 0
            fi
        fi
    done
    return 1
}

echo ""
echo "========================================"
echo "   Vishwa Autocomplete Installer"
echo "========================================"
echo ""

OS=$(detect_os)
print_step "Detected OS: $OS"

# Find Python
print_step "Looking for Python 3..."
PYTHON=$(find_python)
if [ -z "$PYTHON" ]; then
    print_error "Python 3 not found. Please install Python 3.8+ first."
    echo ""
    echo "Installation instructions:"
    echo "  macOS:   brew install python3"
    echo "  Ubuntu:  sudo apt install python3 python3-venv"
    echo "  Fedora:  sudo dnf install python3"
    echo "  Windows: https://www.python.org/downloads/"
    exit 1
fi

PYTHON_VERSION=$("$PYTHON" --version 2>&1)
print_success "Found $PYTHON_VERSION ($PYTHON)"

# Set up directories
VISHWA_DIR="$HOME/.vishwa"
VENV_DIR="$VISHWA_DIR/venv"

print_step "Setting up Vishwa directory at $VISHWA_DIR..."

# Create directory
mkdir -p "$VISHWA_DIR"

# Check if venv already exists
if [ -d "$VENV_DIR" ]; then
    print_warning "Virtual environment already exists at $VENV_DIR"
    read -p "Do you want to recreate it? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$VENV_DIR"
    else
        print_step "Using existing virtual environment..."
    fi
fi

# Create virtual environment if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    print_step "Creating virtual environment..."
    "$PYTHON" -m venv "$VENV_DIR"
    print_success "Virtual environment created"
fi

# Determine pip path based on OS
if [ "$OS" = "windows" ]; then
    PIP="$VENV_DIR/Scripts/pip"
    PYTHON_VENV="$VENV_DIR/Scripts/python"
else
    PIP="$VENV_DIR/bin/pip"
    PYTHON_VENV="$VENV_DIR/bin/python"
fi

# Upgrade pip
print_step "Upgrading pip..."
"$PIP" install --upgrade pip -q

# Install vishwa
print_step "Installing Vishwa..."

# Check if we're in the vishwa source directory (for development)
if [ -f "pyproject.toml" ] && grep -q "name.*vishwa" pyproject.toml 2>/dev/null; then
    print_step "Installing from local source..."
    "$PIP" install -e . -q
else
    # Install from PyPI (when available) or GitHub
    # For now, install from GitHub
    print_step "Installing from GitHub..."
    "$PIP" install git+https://github.com/SrujanArjun/Vishwa.git -q 2>/dev/null || {
        print_error "Failed to install from GitHub. Trying PyPI..."
        "$PIP" install vishwa -q 2>/dev/null || {
            print_error "Vishwa package not found. Please install manually."
            exit 1
        }
    }
fi

print_success "Vishwa installed successfully"

# Verify installation
print_step "Verifying installation..."
if "$PYTHON_VENV" -c "import vishwa.autocomplete.service" 2>/dev/null; then
    print_success "Vishwa autocomplete service is ready"
else
    print_error "Installation verification failed"
    exit 1
fi

# Create .env template if it doesn't exist
ENV_FILE="$VISHWA_DIR/.env"
if [ ! -f "$ENV_FILE" ]; then
    print_step "Creating configuration template..."
    cat > "$ENV_FILE" << 'EOF'
# Vishwa Configuration
# Uncomment and set the model you want to use

# For local models (Ollama)
VISHWA_MODEL=gemma3:4b

# For cloud models (uncomment one)
# VISHWA_MODEL=claude-haiku-4-5
# ANTHROPIC_API_KEY=your-api-key-here

# VISHWA_MODEL=gpt-4o-mini
# OPENAI_API_KEY=your-api-key-here
EOF
    print_success "Configuration template created at $ENV_FILE"
fi

echo ""
echo "========================================"
echo "   Installation Complete"
echo "========================================"
echo ""
echo "Next steps:"
echo ""
echo "  1. Install the VS Code extension:"
echo "     - Open VS Code"
echo "     - Go to Extensions (Ctrl+Shift+X)"
echo "     - Search for 'Vishwa Autocomplete'"
echo "     - Click Install"
echo ""
echo "  2. Configure your model (optional):"
echo "     Edit $ENV_FILE"
echo ""
echo "  3. For local models, install Ollama:"
echo "     https://ollama.ai"
echo "     Then run: ollama pull gemma3:4b"
echo ""
print_warning "If autocomplete doesn't work in other projects:"
echo "  Check VS Code settings - ensure 'vishwa.autocomplete.pythonPath'"
echo "  is set to 'auto' (recommended) or: $PYTHON_VENV"
echo ""
