#!/usr/bin/env bash
#
# Script: export_to_pdf.sh
# Purpose: Wrapper to run export_to_pdf.py which exports all Quarto Reveal.js
#          HTML slides to PDF with full background graphics and images enabled.
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Run Python export script using system/available python3
exec python3 "${SCRIPT_DIR}/export_to_pdf.py" "$@"
