#!/usr/bin/env python3
"""
ADVOKAT MCP Server
Verbindet Claude direkt mit der ADVOKAT SQL-Datenbank.

Konfiguration via Umgebungsvariablen:
  ADVOKAT_DB_HOST   - Hostname oder IP des SQL Servers (z.B. 192.168.1.21)
  ADVOKAT_DB_PORT   - TCP-Port des SQL Servers (z.B. 49689 bei named instance)
  ADVOKAT_DB_USER   - SQL Server Login (z.B. advokat_mcp)
  ADVOKAT_DB_PASS   - Passwort des SQL Server Logins
  ADVOKAT_DB_NAME   - Datenbankname (Standard: Advokat_DATEN)
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Any
import pymssql
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp import types

# ── Konfiguration via Umgebungsvariablen ───────────────────────────────────────
_host = os.environ.get("ADVOKAT_DB_HOST", "")
_port = os.environ.get("ADVOKAT_DB_PORT", "1433")
_user = os.environ.get("ADVOKAT_DB_USER", "")
_pass = os.environ.get("ADVOKAT_DB_PASS", "")
_db   = os.environ.get("ADVOKAT_DB_NAME", "Advokat_DATEN")

if not _host or not _user or not _pass:
    print(
        "FEHLER: Umgebungsvariablen fehlen.\n"
        "Bitte setzen: ADVOKAT_DB_HOST, ADVOKAT_DB_USER, ADVOKAT_DB_PASS\n"
        "Optional:     ADVOKAT_DB_PORT (Standard: 1433), ADVOKAT_DB_NAME (Standard: Advokat_DATEN)",
        file=sys.stderr,
    )
    sys.exit(1)

DB_CONFIG = {
    "server": _host,
    "port": int(_port),
    "user": _user,
    "password": _pass,
    "login_timeout": 10,
    "charset": "UTF-8",
}
DEFAULT_DB = _db

# ── DB-Hilfsfunktionen ─────────────────────────────────────────────────────────

def get_conn(database: str = None):
    return pymssql.connect(database=database or DEFAULT_DB, **DB_CONFIG)


def rows_to_dicts(cursor) -> list[dict]:
    cols = [d[0] for d in cursor.description]
    return [
        {k: (v.isoformat() if isinstance(v, datetime) else v)
         for k, v in zip(cols, row)}
        for row in cursor.fetchall()
    ]


def fmt(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ── MCP Server ─────────────────────────────────────────────────────────────────

server = Server("advokat-connect")


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="suche_akt",
            description=(
                "Sucht Akten in ADVOKAT. Kann nach Aktenkurzbezeichnung, Causa, "
                "Klientenname, Gegner oder Status filtern. Gibt Aktennummer, Causa, "
                "Klient, Gegner, RA, Status und Anlagedatum zurück."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "suchbegriff": {
                        "type": "string",
                        "description": "Freitext-Suche in Aktenkurz und Causa"
                    },
                    "klient_name": {
                        "type": "string",
                        "description": "Name des Klienten (Teilstring)"
                    },
                    "status": {
                        "type": "string",
                        "description": "Akten-Status (z.B. leer=offen, 'erledigt')"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max. Anzahl Ergebnisse (Standard: 20)",
                        "default": 20
                    }
                }
            }
        ),
        types.Tool(
            name="get_akt_details",
            description=(
                "Gibt alle Details zu einem Akt zurück: Stammdaten, Klient, Gegner, "
                "Gericht, RA/SB, Bemessungsgrundlagen, Memo."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "anr": {
                        "type": "integer",
                        "description": "Aktennummer (ANr)"
                    }
                },
                "required": ["anr"]
            }
        ),
        types.Tool(
            name="suche_person",
            description=(
                "Sucht Personen/Firmen im ADVOKAT-Personenstamm nach Name, Vorname, "
                "Ort oder Namenskurzbezeichnung."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Nachname oder Firmenname (Teilstring)"
                    },
                    "vorname": {
                        "type": "string",
                        "description": "Vorname (Teilstring)"
                    },
                    "ort": {
                        "type": "string",
                        "description": "Ort (Teilstring)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max. Ergebnisse (Standard: 20)",
                        "default": 20
                    }
                }
            }
        ),
        types.Tool(
            name="get_leistungen",
            description=(
                "Gibt alle Leistungen (Honorareinträge) zu einem Akt zurück. "
                "Enthält Datum, Leistungskürzel, Verdienst, SB, Barauslagen."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "anr": {
                        "type": "integer",
                        "description": "Aktennummer"
                    },
                    "von": {
                        "type": "string",
                        "description": "Von-Datum (YYYY-MM-DD)"
                    },
                    "bis": {
                        "type": "string",
                        "description": "Bis-Datum (YYYY-MM-DD)"
                    }
                },
                "required": ["anr"]
            }
        ),
        types.Tool(
            name="get_offene_posten",
            description=(
                "Gibt offene Honorarforderungen zurück. Kann nach Aktennummer "
                "oder Person gefiltert werden. Zeigt Rechnungsnummer, Betrag, "
                "Offen-Betrag, Mahnstufe, Fälligkeitsdatum."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "anr": {
                        "type": "integer",
                        "description": "Aktennummer (optional)"
                    },
                    "nur_offene": {
                        "type": "boolean",
                        "description": "Nur Posten mit Offen > 0 (Standard: true)",
                        "default": True
                    }
                }
            }
        ),
        types.Tool(
            name="get_termine",
            description=(
                "Gibt Termine zurück. Kann nach Aktennummer oder Datumsbereich "
                "gefiltert werden."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "anr": {
                        "type": "integer",
                        "description": "Aktennummer (optional)"
                    },
                    "von": {
                        "type": "string",
                        "description": "Von-Datum (YYYY-MM-DD)"
                    },
                    "bis": {
                        "type": "string",
                        "description": "Bis-Datum (YYYY-MM-DD)"
                    },
                    "nur_offene": {
                        "type": "boolean",
                        "description": "Nur nicht erledigte Termine",
                        "default": True
                    }
                }
            }
        ),
        types.Tool(
            name="get_dokumente",
            description=(
                "Listet Dokumente zu einem Akt auf. Enthält Betreff (vom Anwalt "
                "oft manuell ergänzt) und Memo — die wichtigsten Felder zum "
                "Wiederfinden von Dokumenten."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "anr": {
                        "type": "integer",
                        "description": "Aktennummer"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max. Ergebnisse (Standard: 50)",
                        "default": 50
                    }
                },
                "required": ["anr"]
            }
        ),
        types.Tool(
            name="suche_dokument",
            description=(
                "Sucht Dokumente quer über alle Akten nach Stichwörtern in Betreff "
                "und/oder Memo. Ideal zum Wiederfinden von Schriftstücken wenn man "
                "den Akt nicht mehr genau weiß."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "betreff": {
                        "type": "string",
                        "description": "Suchbegriff im Betreff-Feld"
                    },
                    "memo": {
                        "type": "string",
                        "description": "Suchbegriff im Memo-Feld"
                    },
                    "von": {
                        "type": "string",
                        "description": "Von-Datum (YYYY-MM-DD)"
                    },
                    "bis": {
                        "type": "string",
                        "description": "Bis-Datum (YYYY-MM-DD)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max. Ergebnisse (Standard: 30)",
                        "default": 30
                    }
                }
            }
        ),
        types.Tool(
            name="get_akten_uebersicht",
            description=(
                "Gibt eine Übersicht aller offenen Akten mit Klient, Causa, RA/SB "
                "und letzter Aktivität. Nützlich für Tagesüberblick."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "ra": {
                        "type": "string",
                        "description": "Filter auf bestimmten RA (Kürzel)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max. Ergebnisse (Standard: 50)",
                        "default": 50
                    }
                }
            }
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:

    try:
        if name == "suche_akt":
            result = await asyncio.to_thread(_suche_akt, arguments)
        elif name == "get_akt_details":
            result = await asyncio.to_thread(_get_akt_details, arguments)
        elif name == "suche_person":
            result = await asyncio.to_thread(_suche_person, arguments)
        elif name == "get_leistungen":
            result = await asyncio.to_thread(_get_leistungen, arguments)
        elif name == "get_offene_posten":
            result = await asyncio.to_thread(_get_offene_posten, arguments)
        elif name == "get_termine":
            result = await asyncio.to_thread(_get_termine, arguments)
        elif name == "get_dokumente":
            result = await asyncio.to_thread(_get_dokumente, arguments)
        elif name == "suche_dokument":
            result = await asyncio.to_thread(_suche_dokument, arguments)
        elif name == "get_akten_uebersicht":
            result = await asyncio.to_thread(_get_akten_uebersicht, arguments)
        else:
            result = {"error": f"Unbekanntes Tool: {name}"}

        return [types.TextContent(type="text", text=fmt(result))]

    except Exception as e:
        return [types.TextContent(type="text", text=fmt({"error": str(e)}))]


# ── Tool-Implementierungen ─────────────────────────────────────────────────────

def _suche_akt(args: dict) -> list[dict]:
    limit = args.get("limit", 20)
    where = ["1=1"]
    params = []

    suchbegriff = args.get("suchbegriff", "").strip()
    if suchbegriff:
        where.append("(a.AKurz LIKE %s OR a.Causa LIKE %s)")
        params += [f"%{suchbegriff}%", f"%{suchbegriff}%"]

    klient_name = args.get("klient_name", "").strip()
    if klient_name:
        where.append("(n.Name1 LIKE %s OR n.Vorname LIKE %s OR n.Name2 LIKE %s)")
        params += [f"%{klient_name}%"] * 3

    status = args.get("status", "").strip()
    if status == "offen":
        where.append("(a.ErledDat IS NULL AND a.Status NOT LIKE 'erledigt')")
    elif status:
        where.append("a.Status LIKE %s")
        params.append(f"%{status}%")

    sql = f"""
        SELECT TOP ({limit})
            a.ANr, a.AKurz, a.Causa, a.Status, a.RA, a.SB,
            a.AnlagDat, a.ErledDat,
            n.Name1 + ISNULL(' ' + n.Vorname, '') AS Klient,
            g.Name1 + ISNULL(' ' + g.Vorname, '') AS Gegner
        FROM Akten a
        LEFT JOIN Namen n ON n.NNr = a.Klient1
        LEFT JOIN Namen g ON g.NNr = a.Gegner1
        WHERE {' AND '.join(where)}
        ORDER BY a.ANr DESC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur)


def _get_akt_details(args: dict) -> dict:
    anr = args["anr"]
    sql = """
        SELECT
            a.*,
            n.Name1 + ISNULL(' ' + n.Vorname, '') AS KlientName,
            n.Straße AS KlientStraße, n.Plz AS KlientPlz, n.Ort AS KlientOrt,
            n.NKurz AS KlientKurz,
            g.Name1 + ISNULL(' ' + g.Vorname, '') AS GegnerName,
            g.NKurz AS GegnerKurz,
            ge.Name1 AS GerichtName
        FROM Akten a
        LEFT JOIN Namen n ON n.NNr = a.Klient1
        LEFT JOIN Namen g ON g.NNr = a.Gegner1
        LEFT JOIN Namen ge ON ge.NNr = a.Gericht1
        WHERE a.ANr = %s
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, (anr,))
        rows = rows_to_dicts(cur)
        return rows[0] if rows else {"error": f"Akt {anr} nicht gefunden"}


def _suche_person(args: dict) -> list[dict]:
    limit = args.get("limit", 20)
    where = ["1=1"]
    params = []

    name = args.get("name", "").strip()
    if name:
        where.append("(n.Name1 LIKE %s OR n.Name2 LIKE %s OR n.NKurz LIKE %s)")
        params += [f"%{name}%"] * 3

    vorname = args.get("vorname", "").strip()
    if vorname:
        where.append("n.Vorname LIKE %s")
        params.append(f"%{vorname}%")

    ort = args.get("ort", "").strip()
    if ort:
        where.append("n.Ort LIKE %s")
        params.append(f"%{ort}%")

    sql = f"""
        SELECT TOP ({limit})
            n.NNr, n.NKurz, n.Vorname, n.Name1, n.Name2,
            n.FirmaJN, n.Titel, n.Geschlecht,
            n.Straße, n.Plz, n.Ort,
            n.geboren, n.Memo,
            (SELECT COUNT(*) FROM Akten a WHERE a.Klient1 = n.NNr) AS AnzahlAkten
        FROM Namen n
        WHERE {' AND '.join(where)}
        ORDER BY n.Name1, n.Vorname
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur)


def _get_leistungen(args: dict) -> list[dict]:
    anr = args["anr"]
    params = [anr]
    where = ["l.ANr = %s"]

    if args.get("von"):
        where.append("l.Datum >= %s")
        params.append(args["von"])
    if args.get("bis"):
        where.append("l.Datum <= %s")
        params.append(args["bis"])

    sql = f"""
        SELECT
            l.Zähler, l.Datum, l.Leistung, l.SB,
            l.Verdienst, l.Zuschlag,
            l.BA1Art, l.BA1Betrag, l.BA2Art, l.BA2Betrag, l.BA3Art, l.BA3Betrag,
            l.Memo, l.Kommentar, l.DatumAbrechnung, l.Status,
            l.Intern
        FROM Leistung l
        WHERE {' AND '.join(where)}
        ORDER BY l.Datum DESC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        rows = rows_to_dicts(cur)

    # Summen anhängen
    total_verdienst = sum(r.get("Verdienst") or 0 for r in rows)
    total_ba = sum(
        (r.get("BA1Betrag") or 0) + (r.get("BA2Betrag") or 0) + (r.get("BA3Betrag") or 0)
        for r in rows
    )
    return {
        "leistungen": rows,
        "summe_verdienst": round(total_verdienst, 2),
        "summe_barauslagen": round(total_ba, 2),
        "anzahl": len(rows)
    }


def _get_offene_posten(args: dict) -> list[dict]:
    where = ["1=1"]
    params = []

    if args.get("anr"):
        where.append("op.Anr = %s")
        params.append(args["anr"])

    if args.get("nur_offene", True):
        where.append("op.Offen > 0")

    sql = f"""
        SELECT
            op.Zähler, op.Anr, op.Datum, op.Faelligkeitsdatum,
            op.RechnungsNr1, op.RechnungsNr2, op.Betreff,
            op.Anforderung, op.Offen, op.Zahlung, op.Storno,
            op.Mahnstufe, op.Mahndatum, op.Art,
            n.Name1 + ISNULL(' ' + n.Vorname, '') AS Person,
            a.AKurz, a.Causa
        FROM OffenePosten op
        LEFT JOIN Namen n ON n.NNr = op.Person
        LEFT JOIN Akten a ON a.ANr = op.Anr
        WHERE {' AND '.join(where)}
        ORDER BY op.Faelligkeitsdatum ASC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur)


def _get_termine(args: dict) -> list[dict]:
    where = ["1=1"]
    params = []

    if args.get("anr"):
        where.append("t.ANr = %s")
        params.append(args["anr"])

    if args.get("von"):
        where.append("t.Datum >= %s")
        params.append(args["von"])

    if args.get("bis"):
        where.append("t.Datum <= %s")
        params.append(args["bis"])

    if args.get("nur_offene", True):
        where.append("t.Erledigt = 0")

    sql = f"""
        SELECT
            t.Zähler, t.ANr, t.Datum, t.Zeit, t.Ende,
            t.Betreff, t.SB, t.Art, t.Erledigt, t.Memo,
            a.AKurz, a.Causa
        FROM Termin t
        LEFT JOIN Akten a ON a.ANr = t.ANr
        WHERE {' AND '.join(where)}
        ORDER BY t.Datum ASC, t.Zeit ASC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur)


def _get_dokumente(args: dict) -> list[dict]:
    anr = args["anr"]
    limit = args.get("limit", 50)
    sql = f"""
        SELECT TOP ({limit})
            d.Zähler, d.Datum, d.SB, d.VonSB,
            d.Betreff, d.Memo, d.Dokument,
            d.DokumentArt, d.MailAdresse, d.Status,
            d.AttachmentCount, d.AttachmentFileNames
        FROM Dokument d
        WHERE d.Anr = %s
        ORDER BY d.Datum DESC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, (anr,))
        return rows_to_dicts(cur)


def _suche_dokument(args: dict) -> list[dict]:
    limit = args.get("limit", 30)
    where = ["1=1"]
    params = []

    betreff = args.get("betreff", "").strip()
    if betreff:
        where.append("d.Betreff LIKE %s")
        params.append(f"%{betreff}%")

    memo = args.get("memo", "").strip()
    if memo:
        where.append("d.Memo LIKE %s")
        params.append(f"%{memo}%")

    if not betreff and not memo:
        return {"error": "Bitte mindestens 'betreff' oder 'memo' angeben."}

    if args.get("von"):
        where.append("d.Datum >= %s")
        params.append(args["von"])
    if args.get("bis"):
        where.append("d.Datum <= %s")
        params.append(args["bis"])

    sql = f"""
        SELECT TOP ({limit})
            d.Zähler, d.Anr, d.Datum, d.SB,
            d.Betreff, d.Memo, d.Dokument, d.DokumentArt,
            a.AKurz, a.Causa,
            n.Name1 + ISNULL(' ' + n.Vorname, '') AS Klient
        FROM Dokument d
        LEFT JOIN Akten a ON a.ANr = d.Anr
        LEFT JOIN Namen n ON n.NNr = a.Klient1
        WHERE {' AND '.join(where)}
        ORDER BY d.Datum DESC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur)


def _get_akten_uebersicht(args: dict) -> list[dict]:
    limit = args.get("limit", 50)
    where = ["a.ErledDat IS NULL"]
    params = []

    if args.get("ra"):
        where.append("a.RA = %s")
        params.append(args["ra"])

    sql = f"""
        SELECT TOP ({limit})
            a.ANr, a.AKurz, a.Causa, a.RA, a.SB, a.Status,
            a.AnlagDat, a.FristDat,
            n.Name1 + ISNULL(' ' + n.Vorname, '') AS Klient,
            g.Name1 + ISNULL(' ' + g.Vorname, '') AS Gegner,
            (SELECT MAX(l.Datum) FROM Leistung l WHERE l.ANr = a.ANr) AS LetzteLeistung,
            (SELECT COUNT(*) FROM Leistung l WHERE l.ANr = a.ANr) AS AnzahlLeistungen
        FROM Akten a
        LEFT JOIN Namen n ON n.NNr = a.Klient1
        LEFT JOIN Namen g ON g.NNr = a.Gegner1
        WHERE {' AND '.join(where)}
        ORDER BY a.ANr DESC
    """
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        return rows_to_dicts(cur)


# ── Einstiegspunkt ─────────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

if __name__ == "__main__":
    asyncio.run(main())
