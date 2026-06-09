# ADVOKAT Connect — MCP Server

**ADVOKAT** ist die meistverbreitete Anwaltssoftware in Österreich und wird von tausenden Kanzleien für Aktenführung, Leistungserfassung, Dokumentenverwaltung und Buchhaltung genutzt.

Dieser Server ist ein unabhängiges Community-Projekt und steht in **keiner Verbindung mit der ADVOKAT Unternehmensberatung GREITER & GREITER GmbH**.

---

## Was ist das?

ADVOKAT Connect ist ein [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) Server, der KI-Assistenten direkt mit der ADVOKAT-Datenbank verbindet — ohne Bildschirmsteuerung, direkt via SQL.

Statt mühsam durch Menüs zu navigieren, kann man einfach in natürlicher Sprache fragen:

> *„Welche offenen Akten gibt es für den Klienten Huber?"*
> *„Zeig mir alle Dokumente zum Thema Kaufvertrag aus den letzten 3 Monaten."*
> *„Was ist der aktuelle Status des Verfahrens gegen die XY GmbH?"*

Der KI-Assistent übersetzt die Frage in eine Datenbankabfrage und liefert die Antwort direkt aus ADVOKAT — in Sekunden, ohne einen einzigen Klick.

### Funktioniert mit

| Client | Modell-Art | Datenschutz |
|---|---|---|
| **Claude Desktop** (Anthropic) | Cloud | Daten gehen an Anthropic |
| **ChatGPT Desktop** (OpenAI) | Cloud | Daten gehen an OpenAI |
| **MSTY Studio** | Cloud oder lokal | Vollständig lokal möglich |
| **LM Studio** | Lokal | Daten bleiben in der Kanzlei |
| **Mistral Vibe** | Cloud oder lokal | Je nach Konfiguration |
| Jeder andere MCP-kompatible Client | — | — |

> **Hinweis für lokale Modelle:** Das verwendete Modell muss Tool Calling / Function Calling unterstützen. Aktuell gut geeignet sind **Qwen3 6B+** und **Gemma 4** — beide liefern zuverlässiges Tool Calling auch in kleineren Varianten. Bei sehr kleinen Modellen (unter 4B) kann die Qualität schwanken.

---

## Voraussetzungen

- **ADVOKAT** mit MS SQL Server 2019 (oder neuer)
- **Python 3.11+** (empfohlen: 3.12 via Homebrew auf macOS)
- **FreeTDS** (macOS: `brew install freetds`)
- **Claude Desktop**, **MSTY Studio** oder ein anderer MCP-Client

---

## SQL Server: Read-Only Login anlegen

Im SQL Server Management Studio (SSMS) als `sa` verbinden und folgendes Script ausführen:

```sql
-- Login anlegen
CREATE LOGIN advokat_mcp
    WITH PASSWORD = 'IhrSicheresPasswort!',
         CHECK_POLICY = ON,
         CHECK_EXPIRATION = OFF;

-- User in Advokat_DATEN anlegen
USE Advokat_DATEN;
CREATE USER advokat_mcp FOR LOGIN advokat_mcp;

-- Nur Lesezugriff
ALTER ROLE db_datareader ADD MEMBER advokat_mcp;
```

> Wähle ein starkes Passwort (Groß/Klein/Zahl/Sonderzeichen).

### Named Instance: TCP-Port ermitteln

Bei ADVOKAT läuft SQL Server typischerweise als named instance (z.B. `SERVER\ADVOKAT`).
Den dynamischen TCP-Port einmalig so ermitteln (macOS/Linux Terminal):

```bash
python3 -c "
import socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(3)
sock.sendto(b'\x04', ('IP-DES-SERVERS', 1434))
data, _ = sock.recvfrom(4096)
print(data[3:].decode('utf-8'))
"
```

In der Ausgabe den Wert bei `tcp=XXXXX` ablesen und als `ADVOKAT_DB_PORT` eintragen.

---

## Installation (macOS)

```bash
# Repository klonen
git clone https://github.com/DEIN_USERNAME/advokat-connect-mcp.git
cd advokat-connect-mcp

# Python venv erstellen (mit Homebrew Python 3.12)
/opt/homebrew/bin/python3.12 -m venv venv

# pymssql mit FreeTDS kompilieren + mcp installieren
FREETDS=$(brew --prefix freetds)
CFLAGS="-I$FREETDS/include" LDFLAGS="-L$FREETDS/lib" \
  venv/bin/pip install -r requirements.txt --no-cache-dir

# Installation prüfen
venv/bin/python -c "import pymssql; print('pymssql:', pymssql.__version__)"
venv/bin/python -c "import mcp; print('mcp:', mcp.__version__)"
```

> Tipp: `setup_macos.command` doppelklicken für automatisches Setup.

---

## Konfiguration

Die Datenbankzugangsdaten werden als Umgebungsvariablen übergeben — nie im Code, nie in git.

### Claude Desktop (`~/Library/Application Support/Claude/claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "advokat": {
      "command": "/Users/DEINNAME/advokat-connect-mcp/venv/bin/python",
      "args": ["/Users/DEINNAME/advokat-connect-mcp/advokat_mcp_server.py"],
      "env": {
        "ADVOKAT_DB_HOST": "IP-DES-SERVERS",
        "ADVOKAT_DB_PORT": "49689",
        "ADVOKAT_DB_USER": "advokat_mcp",
        "ADVOKAT_DB_PASS": "IhrPasswort"
      }
    }
  }
}
```

Nach dem Speichern Claude Desktop neu starten.

### MSTY Studio — mit lokalem Modell (vollständig privat)

1. **Settings → Toolbox → Add New Tool**
2. Transport: **STDIO / JSON**
3. JSON-Konfiguration eintragen:

```json
{
  "command": "/Users/DEINNAME/advokat-connect-mcp/venv/bin/python",
  "args": ["/Users/DEINNAME/advokat-connect-mcp/advokat_mcp_server.py"],
  "env": {
    "ADVOKAT_DB_HOST": "IP-DES-SERVERS",
    "ADVOKAT_DB_PORT": "49689",
    "ADVOKAT_DB_USER": "advokat_mcp",
    "ADVOKAT_DB_PASS": "IhrPasswort"
  }
}
```

4. Name: `ADVOKAT Connect` → **Add**
5. Als Modell ein lokales Modell mit Tool Calling wählen (z.B. **Qwen3 6B** oder **Gemma 4** via Ollama oder LM Studio)

Mit MSTY und einem lokalen Modell bleiben **alle Anfragen und Kanzleidaten lokal** — es werden keine Daten an externe Server übertragen.

---

## Verfügbare Tools

| Tool | Beschreibung |
|---|---|
| `suche_akt` | Sucht Akten nach Suchbegriff, Klientenname oder Status |
| `get_akt_details` | Vollständige Aktenstammdaten inkl. Klient, Gegner, Gericht |
| `suche_person` | Personenstamm durchsuchen nach Name, Vorname, Ort |
| `get_leistungen` | Leistungserfassung eines Akts mit Honorar-Summen |
| `get_offene_posten` | Offene Honorarforderungen |
| `get_termine` | Termine gefiltert nach Akt oder Datumsbereich |
| `get_dokumente` | Dokumentliste eines Akts (Betreff + Memo) |
| `suche_dokument` | Volltext-Suche in Betreff/Memo quer über alle Akten |
| `get_akten_uebersicht` | Alle offenen Akten mit letzter Aktivität |

---

## Beispielanfragen

```
Welche offenen Akten gibt es für den Klienten Huber?
Zeig mir alle Dokumente zum Thema Mietvertrag aus diesem Jahr
Suche Dokumente mit dem Stichwort "Kaufvertrag" im Betreff
Was sind die letzten Leistungen im Akt 1234?
Welche Termine stehen diese Woche an?
Zeig mir alle Akten gegen die Mustermann GmbH
```

---

## Datenschutz & Sicherheit

- Der SQL-Login hat ausschließlich **Leserechte** (`db_datareader`) — keine Schreiboperationen möglich
- Bei Verwendung mit lokalem Modell (Ollama/LM Studio) verlässt **kein einziges Wort** die Kanzlei
- Credentials werden als Umgebungsvariablen übergeben — nie im Code, nie in git
- Die `.env` Datei ist in `.gitignore` ausgeschlossen

---

## Lizenz

MIT License — freie Verwendung, auch für kommerzielle Kanzleien.

---

*Dieses Projekt steht in keiner Verbindung mit der ADVOKAT Unternehmensberatung GREITER & GREITER GmbH.*
