# CustomCRM – Funktionsübersicht

## Accounts (Kommunen)
- Anlegen, bearbeiten, archivieren, löschen
- Accounttypen (Stadt kreisfrei, Landkreis, Region, …) konfigurierbar
- Bundesland-Zuordnung
- Besitzer-Zuweisung (Accountmanager)
- Volltextsuche
- Filterung nach Typ, Phase, Produkt, Bundesland, Besitzer
- CSV-Export
- Soft-Delete (Archivierung)

## Kontakte
- Mehrere Kontakte pro Account
- Primärkontakt-Flag
- Archivierung

## Produkte & Phasen
- Mehrere Produkte pro Account (AccountProduct)
- Dynamische Phasen je Produkt (konfigurierbar)
- Benutzerdefinierte Felder pro Produkt (Datum, Integer, Boolean)
- Verantwortliche Person pro Produkt

## Verträge
- Mehrere Verträge pro Account
- Vertragstypen konfigurierbar (aktivierbar/deaktivierbar)
- Automatische Verlängerungsberechnung
- Kündigungsfrist & Verlängerungsintervall
- PDF-Dokument-Upload (mehrere Dateien pro Vertrag)
- Enddatum-Berechnung inkl. Verlängerungen
- Vertragsübersicht mit Ablauf-Markierung

## Aktivitäten & Aufgaben
- Aktivitätslog pro Account (Anruf, E-Mail, Meeting, Aufgabe)
- Dateianhang pro Aktivität
- Todos mit Fälligkeitsdatum und Erledigt-Status
- Globale Todo-Liste über alle Accounts

## Kampagnen
- Kampagnen mit Kontakt-Snapshots (denormalisiert)
- Accounts zu Kampagnen hinzufügen
- Erfolgs-Status pro Kontakt togglebar
- Kontakte aus Kampagne entfernen

## Dashboards & Auswertung
- **Superuser-Dashboard:** Vertragspartner pro Accountmanager (mit Ampelbewertung), Pipeline, Vertragstypen, auslaufende Verträge (90 Tage), inaktive Partner (90 Tage)
- **Verwalter-Dashboard:** eigene Accounts, offene Todos
- **Pipeline-Ansicht:** Accounts in offenen Phasen, sortiert nach letzter Aktivität, Wartezeit-Badges
- **Analyse-Seite:** Kundenzufriedenheit nach Jahr und Bundesland

## Qualitätsdaten (Integreat-spezifisch)
- **Region Health / Ampelbewertung:** CSV-Upload, automatische Grün/Gelb/Rot-Berechnung aus 6 Metriken
- **Umfrage-Historie:** LimeSurvey-Import (2020–2025), Zufriedenheitstrends, Feature-Wünsche, ungenutzte Features

## Benutzerverwaltung & Rollen
- Zwei Rollen: Superuser (global) und Verwalter (nur eigene Accounts)
- Benutzerverwaltung im Admin-Bereich
- OIDC/Keycloak-Integration (optional)
- Passwort ändern

## System
- Einstellungen: Accounttypen, Produkte, Phasen, Felder, Vertragstypen, Benutzer
- Geschützte Mediadateien (nur für eingeloggte Nutzer)
- Versionierung (CalVer) mit Changelog

## Fehlende typische CRM-Features
- E-Mail-Integration (nur manuelles Log, kein Postfach-Sync)
- Angebotserstellung
- Lead-Management
- Reporting/Exports über Kampagnen hinaus
- Kalender-Integration
- API
