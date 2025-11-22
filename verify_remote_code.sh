#!/bin/bash
# Generate SHA256 checksums for repository files on remote server
# This script should be uploaded to the server and run there
# Usage: ./verify_remote_code.sh [project_directory]

set -e

# Default project directory (adjust if your server uses a different path)
PROJECT_DIR="${1:-$HOME/polymarket}"

echo "=========================================="
echo "Remote Code Verification"
echo "=========================================="
echo ""

# Check if project directory exists
if [ ! -d "$PROJECT_DIR" ]; then
    echo "❌ Error: Project directory not found: $PROJECT_DIR"
    echo ""
    echo "Usage: $0 [project_directory]"
    echo "Example: $0 /home/ubuntu/polymarket"
    exit 1
fi

cd "$PROJECT_DIR"

# Detect checksum command (OS-agnostic: try sha256sum first for Linux, then shasum)
if command -v sha256sum >/dev/null 2>&1; then
    CHECKSUM_CMD="sha256sum"
elif command -v shasum >/dev/null 2>&1; then
    CHECKSUM_CMD="shasum -a 256"
else
    echo "❌ Error: Neither 'sha256sum' nor 'shasum' command found"
    echo "Please install one of these tools to generate checksums"
    exit 1
fi

# Collect files to verify
# Use git ls-files if available, otherwise use find
if command -v git >/dev/null 2>&1 && git rev-parse --git-dir >/dev/null 2>&1; then
    # Get all tracked files matching patterns
    FILES=$(git ls-files | grep -E '\.(py|service|timer)$|^(requirements\.txt|env\.example)$' | sort)
else
    # Fallback: use find if git is not available
    echo "⚠️  Git not available, using find to locate files..."
    FILES=$(find . -type f \( -name "*.py" -o -name "*.service" -o -name "*.timer" -o -name "requirements.txt" -o -name "env.example" \) ! -path "./.git/*" ! -path "./venv/*" ! -path "./.venv/*" ! -path "./__pycache__/*" | sed 's|^\./||' | sort)
fi

OUTPUT_FILE="remote_checksums.txt"

echo "Computing checksums for repository files..."
echo "Project directory: $PROJECT_DIR"
echo "Using checksum command: $CHECKSUM_CMD"
echo ""

# Clear output file
> "$OUTPUT_FILE"

# Header
echo "==========================================" >> "$OUTPUT_FILE"
echo "Remote Code Checksums - $(date)" >> "$OUTPUT_FILE"
echo "Server: $(hostname)" >> "$OUTPUT_FILE"
echo "==========================================" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

# Count files
FILE_COUNT=$(echo "$FILES" | grep -c . || echo "0")
echo "Found $FILE_COUNT files to verify"
echo ""

# Process each file
for file in $FILES; do
    if [ ! -f "$file" ]; then
        echo "⚠️  WARNING: File not found: $file"
        echo "⚠️  WARNING: $file - NOT FOUND" >> "$OUTPUT_FILE"
        continue
    fi
    
    # Compute SHA256 checksum using detected command
    checksum=$($CHECKSUM_CMD "$file" | awk '{print $1}')
    
    # Get file size (OS-agnostic)
    size=$(stat -c%s "$file" 2>/dev/null || stat -f%z "$file" 2>/dev/null || echo "N/A")
    
    # Get line count
    lines=$(wc -l < "$file" | tr -d ' ')
    
    # Display to console
    echo "📄 $file"
    echo "   Checksum: $checksum"
    echo "   Size:     $size bytes"
    echo "   Lines:    $lines"
    
    # Write to file
    echo "File: $file" >> "$OUTPUT_FILE"
    echo "SHA256: $checksum" >> "$OUTPUT_FILE"
    echo "Size: $size bytes" >> "$OUTPUT_FILE"
    echo "Lines: $lines" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
done

echo "=========================================="
echo "✅ Checksums saved to: $OUTPUT_FILE"
echo "   Verified $FILE_COUNT files"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Download remote_checksums.txt from server"
echo "2. Compare with local_checksums.txt using: diff local_checksums.txt remote_checksums.txt"
echo "3. If checksums don't match, deploy updated files"

