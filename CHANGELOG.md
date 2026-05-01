# Changelog

## 2026.9

### Fehlerbehebungen
- Produkt-Zuweisung: Wenn ein Produkt bereits als archivierter Eintrag im Account vorhanden ist, erscheint jetzt eine verständliche Fehlermeldung statt eines 500-Fehlers

## 2026.8

### Verbesserungen
- Externe Kampagnen: Bearbeiten-Button auf der Account-Detailseite ermöglicht das Ändern von Name, Zeitraum und Anhang
- Kontakt-Formular: Feld „Geschlecht" aus der Oberfläche entfernt (Daten bleiben in der Datenbank erhalten)

### Fehlerbehebungen
- E-Mails: Dropdown „Account zuweisen" wird nicht mehr vom `table-responsive`-Container abgeschnitten

## 2026.7

### Neue Features
- Account-Detailseite: archivierte Produkt-Zuordnungen werden wie archivierte Kontakte als aufklappbarer Abschnitt angezeigt (Wiederherstellen oder endgültig löschen)
- Kontakte: Hauptansprechpersonen haben ein Pflichtfeld „Anrede" (Freitext, z.B. „Sehr geehrte Frau Muster")
- Das Anrede-Feld wird im UI nur eingeblendet, wenn „Hauptansprechperson" aktiv ist
- Kampagnen: neue Spalte „Anrede" in der Kontaktliste und im CSV-Export
- Management Command `create_anrede_todos`: erstellt pro Hauptansprechperson ohne Anrede eine Aufgabe beim zuständigen Produktverantwortlichen (bzw. Account-Inhaber)

### Verbesserungen
- AccountProduct: Unique-Constraint verhindert doppelte Produkt-Zuordnung zum selben Account
- AccountProduct: Kreisreferenz im Produktverbund wird beim Speichern erkannt und verhindert
- Account-Detailseite: Kampagnen werden nach Startdatum sortiert (neueste zuerst)
- Kampagnen-Formular: Enddatum darf nicht vor Startdatum liegen (Fehler wird angezeigt)
- Vertrag-Formular: Laufzeit muss mindestens 1 Monat betragen; bei festem Enddatum ist kein Verlängerungsintervall mehr eingebbar
- Region-Health-Upload: Weiterleitung zur manuellen Zuordnung enthält jetzt die Upload-ID, sodass parallele Uploads verschiedener Superuser sich nicht gegenseitig überschreiben
- Region-Health-Zuordnung: Account-Dropdown zeigt nur noch Accounts mit aktivem Integreat-Produkt (Phase „Aktiv")
- Doppelte Kontaktauswahl-Logik für Kampagnen konsolidiert (`campaigns/utils.py`)
- Phase „Beendet" zeigt jetzt eine Fehlermeldung, wenn der Übergang aus der falschen Phase versucht wird (statt lautlos ignoriert zu werden)
- E-Mail-Adresse-Duplikat-Fehler fängt jetzt nur noch `IntegrityError` ab, statt alle Exceptions zu unterdrücken

### Fehlerbehebungen
- Veraltete Testfälle entfernt, die Verwalter-Beschränkung für Kampagnen prüften (Beschränkung wurde bereits früher entfernt)
- Analyse: Partner-Produkte im Produktverbund werden nur einmal (über das Lead-Produkt) gezählt

## 2026.6

### Neue Features
- Produktphase „Abgeschlossen" in allen Produkten in „Aktiv" umbenannt
- Neue Produktphase „Beendet" eingeführt (nur wählbar aus Phase „Aktiv" heraus); erfordert „Beendet zum"-Datum und Beendigungsgrund (Preis / Wettbewerber / Leistung / Interner Grund / Sonstiges)
- Beendigungs-Details werden in der Account-Detailseite im Produkt-Block angezeigt
- Accounts: Bei ausgewähltem Produkt können Ja/Nein-Produktfelder als zusätzliche Filter genutzt werden (z.B. „Suchassistent aktiviert: Ja")
- Analyse: Neuer Abschnitt „Integreat – Produktfelder (Aktiv)" zeigt für jedes Ja/Nein-Feld, wie viele aktive Integreat-Accounts dieses Feld auf „Ja" gesetzt haben
- Aufgaben können einer verantwortlichen Person zugewiesen werden; Standard ist der Aufgabenersteller
- Unter „Aufgaben" werden jetzt alle Aufgaben angezeigt, die dem eingeloggten Nutzer zugewiesen sind – unabhängig vom Account-Eigentümer
- Superuser sehen den Menüpunkt „Aufgaben" jetzt ebenfalls
- Account-Detailseite: zeigt Ersteller und zugewiesene Person pro Aufgabe an
- Datenmigration: bestehende Aufgaben werden automatisch dem Ersteller (bzw. dem Account-Eigentümer als Fallback) zugewiesen

### Verbesserungen
- Pipeline: Spalte „Wartezeit" in „Letzter Kontakt" umbenannt
- Löschdialog für nicht aufgelöste E-Mails auf Standard-Benutzername-Bestätigung umgestellt
- Aktivitäten im Aktivitätenlog können jetzt gelöscht werden (mit Benutzername-Bestätigungs-Dialog)
- Ampelbewertung-Import: Accounts werden jetzt auch dann automatisch gematcht, wenn der Account-Name im System einen Präfix enthält (z.B. „Stadt Dachau" statt „Dachau")
- Ampelbewertung – Manuelle Zuordnung: Alle Dropdowns können auf einmal befüllt und mit einem zentralen „Alle zuordnen"-Button gespeichert werden
- Account-Detailseite: Hinter „Seiten mit niedriger Verständlichkeit" und „Seiten veraltet" wird jetzt der prozentuale Anteil an den Gesamtseiten angezeigt

### Fehlerbehebungen
- Nicht aufgelöste E-Mails: Account-Suchfeld auf kleinen Bildschirmen nicht mehr auf wenige Pixel gequetscht (horizontales Scrollen + Mindestbreite für Eingabefeld)
- Verträge: Aktuelles Enddatum berücksichtigt jetzt die Kündigungsfrist – wenn die Frist für die laufende Verlängerungsperiode bereits verstrichen ist, wird das nächste Enddatum angezeigt

## 2026.5

### Neue Features

- Superuser-Dashboard: Malte-Größenverteilung (klein/mittel/groß) für Produkte in der Phase „Aktiv" wird als Übersichtskarte angezeigt
- Accounts mit mehreren Produkten: Pro Produkt kann eine produktspezifische Hauptansprechperson hinterlegt werden (in der Produkt-Zuordnung bearbeiten; in der Account-Übersicht als eigene Spalte sichtbar)
- Superuser sehen jetzt die Menüpunkte „Meine Kunden" und „Pipeline" für ihre eigenen Accounts (gleiche Logik wie Verwalter-Dashboard)
- Hauptansprechpersonen können nun bei Accounts mit mehreren Produkten einem oder mehreren Produkten zugeordnet werden (Pflege unter Kontakte → Bearbeiten oder beim Anlegen eines neuen Kontakts)
- Kampagnen können einem Produkt zugeordnet werden; beim Hinzufügen von Accounts werden dann produktspezifische Hauptansprechpersonen verwendet (bei Accounts mit nur einem Produkt: Fallback auf alle Hauptansprechpersonen)
- Globaler Kontakt-Export: neue Spalte „Produkt" zeigt, für welches Produkt eine Person als Hauptansprechperson markiert ist

### Fehlerbehebungen

- E-Mail-Erfassung: E-Mails, die an die BCC-Adresse gesendet werden, deren Absenderadresse aber nicht unter „Meine E-Mail-Adressen" hinterlegt ist, werden jetzt abgewiesen statt importiert
- Dashboard / Meine Kunden: Spalte „Regionenzustand" (Ampelbewertung) wird nur noch beim Produkt „Integreat" angezeigt

### Verbesserungen

- Account-Detailseite: Aktivitätenlog oben rechts neben den Stammdaten; kompaktes Layout (Datum, Typ, Betreff) mit scrollbarer Liste
- Analyse: Tabelle „Vertragspartner pro Accountmanager:in (Integreat)" als erster Block in der Analyse-Seite, jetzt für alle Benutzerrollen sichtbar; sortiert nach Anzahl grüner Kommunen (absteigend); CSV-Upload-Button nur noch für Superuser; ⌀ Alter (Gesamt-Zeile) jetzt korrekt als gewichteter Durchschnitt berechnet
- Account-Detailseite: „Integreat-Qualität" und „Umfrage-Historie" werden jetzt im Produkt-Block angezeigt, wenn das Produkt „Integreat" mit der Phase „Abgeschlossen" vorliegt
- Verwalter-Dashboard / Meine Kunden: „Bearbeiten"-Button öffnet jetzt die Account-Detailseite statt der Produkt-Zuordnung
- Account-Übersicht: „Bearbeiten"-Button führt jetzt direkt zur Account-Detailseite
- Account-Detailseite: Stammdaten (Name, Typ, Bundesland, Besitzer, Notizen) sind direkt im Stammdaten-Block bearbeitbar, ohne separate Bearbeiten-Seite
- Verwalter-Dashboard / Meine Kunden: Follower-Accounts im Produktverbund werden nicht mehr als eigene Zeile angezeigt; der Leit-Account zeigt stattdessen ein Badge mit der Anzahl der Verbund-Kommunen
- Kampagnen-CSV-Export: Dateiname wird aus dem Kampagnennamen generiert (statt `kampagne_<id>.csv`)
- Verwalter-Navigation: „Aufgaben" steht jetzt an zweiter Stelle, „Pipeline" an dritter Stelle (direkt nach dem Dashboard)
- Verwalter-Dashboard: Accounts mit Phase „Verloren" werden nicht mehr angezeigt (nur noch „Abgeschlossen")
- Verwalter-Dashboard: Neue Spalte „Regionenzustand" mit Ampelfarbe des Accounts, sofern Daten vorhanden

### Verbesserungen

- Nicht aufgelöste E-Mails: Löschen-Button zum Verwerfen von E-Mails ohne Account-Zuweisung (z. B. versehentlich gesendete Mails)

### Fehlerbehebungen

- E-Mail-Import: Absender mit Komma im Anzeigenamen (z. B. `"Mustermann, Anna" <a.mustermann@example.de>`) wurden nicht korrekt geparst und konnten daher nicht automatisch Accounts zugeordnet werden

## 2026.4

### Neue Features

- Neuer Menüpunkt „Kontakte": alle Kontakte im System durchsuchbar (Name, E-Mail, Telefon), mit Account-Typ, Account-Name und Hauptansprechperson-Kennzeichnung

### Verbesserungen

- Superuser-Dashboard: Tabelle „Vertragspartner pro Accountmanager:in" um Spalten „Pipeline", „⌀ Alter" (Durchschnittsalter der nicht-selbst-endenden Verträge in Jahren) und „Max. Supportstunden" erweitert; Gesamt- und Durchschnittszeile am Tabellenende
- Superuser-Dashboard: separater Block „Pipeline pro Benutzer" entfernt (Daten jetzt in der Ampel-Tabelle)
- Superuser-Dashboard: „Verträge nach Typ" und „Auslaufende Verträge" werden zweispaltig nebeneinander angezeigt
- „Hauptansprechpartner" überall in „Hauptansprechperson" umbenannt

## 2026.3

### Neue Features

- Ampelbewertung (Region Health): Superuser laden die „Region Conditions Summary" CSV hoch; Grün/Gelb/Rot wird automatisch aus Veraltete-Seiten-, HIX- und Broken-Links-Werten berechnet
- Nicht automatisch zugeordnete CSV-Einträge können auf einer separaten Seite manuell einem Account zugewiesen werden
- Account-Detailseite: Health-Box oben rechts zeigt Ampelfarbe, alle 6 Metriken und das Datum des letzten Uploads
- Superuser-Dashboard: Widget „Vertragspartner pro Accountmanager:in" (Ampelbewertung Grün/Gelb/Rot je Manager, sortiert nach Rot desc)
- Neuer Menüpunkt „Analyse" für Superuser: Kundenzufriedenheit nach Jahr (Gesamt, App, Redaktion, Betreuung) und Zufriedenheit pro Bundesland
- LimeSurvey-Umfragedaten (2020–2025) im CRM sichtbar: Zufriedenheitstrends, Feature-Wünsche und ungenutzte Features pro Account
- Account-Detailseite: neues „Umfrage-Historie"-Panel mit farbkodierten Zufriedenheitsbadges, aufklappbaren Details und Feature-Listen
- Neuer Management-Command `import_surveys <verzeichnis>` zum Einlesen von YYYY.csv LimeSurvey-Exporten (mit Aggregation bei mehreren Antworten pro Account)
- Verwalter: neuer Menüpunkt „Pipeline" mit allen Accounts in nicht-abgeschlossenen Phasen, sortiert nach letzter Aktivität (älteste zuerst); Wartezeit-Badges grün/gelb/rot
- Superuser-Dashboard: neues Widget „Auslaufende Verträge" (Verträge mit festem Enddatum in den nächsten 90 Tagen, farbkodiert nach Dringlichkeit)
- Superuser-Dashboard: neues Widget „Inaktive Partner" (aktiver Vertrag, aber keine Aktivität seit über 90 Tagen)

### Verbesserungen

- Superuser-Dashboard umstrukturiert: Vertragspartner pro Accountmanager:in in Zeile 1, Pipeline + Vertragstypen in Zeile 2, dann Auslaufende Verträge, Produkte nach Phase, Inaktive Partner; Widget „Vertragspartner pro Benutzer" entfernt
- Bearbeitungsseiten (Account, Vertrag, Kontakt, Aufgabe, Produkt) übersichtlich neu strukturiert: mehrspaltige Layouts, Card-Gliederung mit Akzentstreifen
- Vertrag bearbeiten: berechnetes Enddatum immer sichtbar in rechter Spalte, Monats- und Euro-Felder mit Einheiten-Suffix
- Datei-Uploads: ansprechende Upload-Zone statt nacktem Datei-Eingabefeld (Vertrag, Aufgabe)
- Vertrags-Liste: abgelaufene Verträge mit festem Enddatum werden ausgegraut und als „Abgelaufen" markiert
- Account-Detailseite: Seitenheader mit Trennlinie, Card-Abschnitte mit gelbem Akzentstreifen, Info-Felder mit Label/Wert-Unterscheidung
- Kampagnen: Verwalter können Kampagnen jetzt vollständig erstellen, bearbeiten, archivieren und löschen

## 2026.2

### Verbesserungen

- Account-Detailseite: "← Zurück"-Button kehrt zur gefilterten Accounts-Liste zurück
- Account-Liste: Filter um Produkt und Phase erweitert (Phase erscheint nur bei ausgewähltem Produkt)
- Account-Liste und Dashboard: Sortierung nach Account-Name war bereits aktiv (keine Änderung nötig)

## 2026.1

### Verbesserungen

- Vertrags-Checkbox umbenannt: "Keine automatische Verlängerung" → "Festes Enddatum"
- Off-by-one-Fehler beim Enddatum behoben: Start 01.04.2024 + 24 Monate ergibt jetzt korrekt 31.03.2026
- Versionsnummer in der Sidebar sichtbar
- CHANGELOG eingeführt
