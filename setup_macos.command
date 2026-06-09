#!/bin/bash
# ADVOKAT MCP Server – macOS Setup
# Doppelklick genügt. Installiert alle Abhängigkeiten und richtet die venv ein.

set -e
cd "$(dirname "$0")"
SCRIPT_DIR="$(pwd)"

echo "================================================="
echo "  ADVOKAT MCP Server – macOS Setup"
echo "================================================="
echo ""

# Python 3.12 suchen
PYTHON=""
for p in /opt/homebrew/bin/python3.12 /usr/local/bin/python3.12 /opt/homebrew/bin/python3 /usr/local/bin/python3; do
    if [ -x "$p" ]; then
        PYTHON="$p"
        break
    fi
done

if [ -z "$PYTHON" ]; then
    echo "FEHLER: Python 3.11+ nicht gefunden."
    echo "Bitte installieren: brew install python@3.12"
    read -p "Enter drücken..."
    exit 1
fi

echo "→ Python: $PYTHON ($($PYTHON --version))"

# FreeTDS prüfen
if ! brew list freetds &>/dev/null 2>&1; then
    echo ""
    echo "→ FreeTDS nicht gefunden – wird installiert..."
    brew install freetds
fi

FREETDS=$(brew --prefix freetds)
echo "→ FreeTDS: $FREETDS"

# venv erstellen
VENV="$SCRIPT_DIR/venv"
echo ""
echo "→ Erstelle Python venv in $VENV ..."
"$PYTHON" -m venv "$VENV"

# Pakete installieren
echo ""
echo "→ Installiere mcp und pymssql (mit FreeTDS) ..."
CFLAGS="-I$FREETDS/include" LDFLAGS="-L$FREETDS/lib" \
    "$VENV/bin/pip" install -r "$SCRIPT_DIR/requirements.txt" \
    --no-cache-dir --quiet

# Prüfung
echo ""
echo "→ Prüfe Installation ..."
"$VENV/bin/python" -c "import mcp; print('  ✓ mcp:', mcp.__version__)"
"$VENV/bin/python" -c "import pymssql; print('  ✓ pymssql:', pymssql.__version__)"

# claude_desktop_config.json updaten
CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
VENV_PYTHON="$VENV/bin/python"
SERVER_SCRIPT="$SCRIPT_DIR/advokat_mcp_server.py"

if [ -f "$CONFIG" ]; then
    echo ""
    echo "→ Aktualisiere Claude Desktop Konfiguration ..."
    "$VENV_PYTHON" << PYEOF
import json, os, sys

config_path = os.path.expanduser("~/Library/Application Support/Claude/claude_desktop_config.json")
venv_python = "$VENV_PYTHON"
server_script = "$SERVER_SCRIPT"

with open(config_path) as f:
    c = json.load(f)

if "mcpServers" not in c:
    c["mcpServers"] = {}

existing = c["mcpServers"].get("advokat", {})

c["mcpServers"]["advokat"] = {
    "command": venv_python,
    "args": [server_script],
    "env": existing.get("env", {
        "ADVOKAT_DB_HOST": "192.168.1.XXX",
        "ADVOKAT_DB_PORT": "1433",
        "ADVOKAT_DB_USER": "advokat_mcp",
        "ADVOKAT_DB_PASS": "PASSWORT_HIER_EINTRAGEN"
    })
}

with open(config_path, "w") as f:
    json.dump(c, f, indent=2, ensure_ascii=False)

print("  ✓ Config gespeichert:", config_path)

env = c["mcpServers"]["advokat"]["env"]
if env.get("ADVOKAT_DB_HOST", "").endswith("XXX") or env.get("ADVOKAT_DB_PASS") == "PASSWORT_HIER_EINTRAGEN":
    print("")
    print("  WICHTIG: Bitte jetzt die Datei öffnen und Credentials eintragen:")
    print("  " + config_path)
    print('  Felder: ADVOKAT_DB_HOST, ADVOKAT_DB_PORT, ADVOKAT_DB_USER, ADVOKAT_DB_PASS')
PYEOF
else
    echo ""
    echo "  Hinweis: Claude Desktop Config nicht gefunden."
    echo "  Bitte manuell konfigurieren – siehe README.md."
    echo "  Python-Pfad: $VENV_PYTHON"
    echo "  Server-Script: $SERVER_SCRIPT"
fi

echo ""
echo "================================================="
echo "  Setup abgeschlossen!"
echo "  1. Credentials in Claude Desktop Config eintragen"
echo "  2. Claude Desktop neu starten"
echo "================================================="
echo ""
read -p "Enter drücken..."
