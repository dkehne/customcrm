# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

German-language Django CRM for municipal customer management. Manages accounts (Kommunen), contacts, products with workflow phases, contracts with auto-renewal logic, and marketing campaigns. Used internally by the digitalfabrik team.

## Commands

```bash
# Development server
python manage.py runserver

# Database migrations
python manage.py migrate
python manage.py makemigrations <app>   # create migrations after model changes

# Run tests
python manage.py test                                        # all tests
python manage.py test accounts                               # single app
python manage.py test accounts.tests.AccountListViewTest     # single class
python manage.py test accounts.tests.AccountListViewTest.test_filter_by_name  # single method

# Linting
python -m pylint core accounts products contracts campaigns emails --load-plugins pylint_django

# Import LimeSurvey exports (YYYY.csv files)
python manage.py import_surveys <verzeichnis>

# Create todos for primary contacts missing an Anrede
python manage.py create_anrede_todos

# Fetch and process inbound emails via IMAP
python manage.py fetch_emails           # single run
python manage.py fetch_emails --daemon  # continuous polling (default: every 5 min)
python manage.py fetch_emails --dry-run # preview without saving

# One-time data migration helpers
python manage.py import_salesforce --owner <username> [--sf-dir <pfad>] [--dry-run]
python manage.py duplicate_account <account_id>  # copies Stammdaten, Kontakte, Produkte, Verträge, Aktivitäten (no Todos/Umfragen/Vertragsdokumente)
```

## Architecture

### Django Apps

- **core**: Project config (settings, urls, wsgi), authentication, user roles, dashboards, analyse view
- **accounts**: Accounts, contacts, activities, todos, region health (Ampelbewertung)
- **products**: Products with dynamic phases and custom fields, Produktverbund
- **contracts**: Contracts with documents, auto-renewal calculations
- **campaigns**: Marketing campaigns with contact snapshots
- **emails**: Inbound email handling, unresolved email tracking

### Key Model Relationships

```
Account
├── Contacts (one-to-many, is_primary flag = Hauptansprechperson)
├── AccountProducts → Product (with current_phase → ProductPhase)
│   ├── AccountProductFieldValues → ProductField (dynamic fields: date/int/bool)
│   └── lead_account_product → AccountProduct (Produktverbund)
├── Contracts → ContractType, ContractDocuments
├── Activities (call/email/meeting/task log)
├── Todos (task list)
└── RegionHealthEntry (Ampelbewertung: green/yellow/red per upload)

Campaign
└── CampaignContacts (denormalized contact snapshots)

SurveySnapshot (LimeSurvey data per account per year)

CustomUser
├── UserEmailAddress (registered sender addresses for matching)
├── UserInboundAddress (system-generated BCC address, 1:1)
└── InboundEmails (processed incoming mail)

Activity → optional InboundEmail → EmailAttachments
```

### Role-Based Access

- `CustomUser.is_superuser` (Django built-in): Full access, sees global statistics dashboard with Ampel-Tabelle, pipeline, contracts, expiring contracts, inactive accounts
- `Verwalter`: Sees only owned accounts, filtered dashboard with upcoming todos and pipeline view

### Common Patterns

- **Soft delete**: `is_archived` boolean on most models
- **Owner filtering**: Non-superusers see only `account__owner=user`
- **Permission checks**: `if not request.user.is_superuser: messages.error(...); return redirect(...)`
- **CSV export**: Semi-colon delimiter, UTF-8-sig encoding, Bundesland display names
- **PDF uploads**: `get_valid_filename(f.name)[:100]` before saving to strip special chars and limit length
- **Forms**: All `ModelForm`s inherit `BootstrapFormMixin` (from `core/utils.py`) which auto-applies Bootstrap CSS classes — no need to add `attrs` manually
- **Model validation**: Django does NOT call `full_clean()` on `save()`. When model-level `clean()` methods matter (e.g. `AccountProduct`), call `full_clean()` explicitly in the view before saving and catch `ValidationError`
- **Tests**: Use `CRMTestCase` from `core.test_helpers` as the base class — it provides ready-made users, accounts, and products

### Produktverbund (Product Groups)

`AccountProduct.lead_account_product` is a self-referential FK. A "follower" product points to its lead. The lead is the canonical representative for statistics — follower products are excluded from counts in the Analyse view. Circular references are caught by `AccountProduct.clean()`.

### Campaign Contact Selection

`campaigns/utils.py:get_contacts_for_product(account, campaign_product, phase_id)` centralises the logic:
- No product on campaign → all `is_primary` contacts
- Account has only one active product → all `is_primary` contacts (regardless of product match)
- Account has multiple active products → only contacts explicitly linked to the matching `AccountProduct` via the `primary_contacts` M2M; returns empty if none assigned

### Contract Auto-Renewal Logic

`Contract.current_end_date()` calculates the actual end date:
- If `is_self_cancelling=True` ("Festes Enddatum") or no renewal interval: returns initial end date
- Otherwise: extends by `renewal_interval_months` until past today

## Configuration

- **Database**: SQLite in development, PostgreSQL in production (via `DATABASE_URL` env var)
- **Production DB**: configured in `/etc/customcrm.env`
- **Custom User Model**: `core.CustomUser`
- **OIDC**: Optional, controlled by `OIDC_ENABLED` env var (Keycloak integration); role `superuser` in JWT `realm_access.roles` grants superuser access
- **Email integration**: `INBOUND_EMAIL_DOMAIN`, `IMAP_HOST`, `IMAP_PORT` (default 993), `IMAP_USER`, `IMAP_PASSWORD`, `IMAP_USE_SSL` (default True)
- **Media uploads**: `media/contract_documents/%Y/%m/` for PDFs
- **Deployment**: Gunicorn + Uvicorn workers, WorkingDirectory `/opt/customcrm/core/`

## Frontend / Design

All list and detail pages follow a consistent design language. When building new list views, use these patterns from `accounts/account_list.html`:

### CSS classes (define per-template in `{% block extra_css %}`)
```css
.page-header      /* h2 + action buttons, border-bottom separator */
.filter-card      /* grey rounded filter/search area */
.filter-card .form-label  /* uppercase, 0.75rem, letter-spacing */
.accounts-table   /* rounded, box-shadow wrapper for tables */
.accounts-table thead th  /* uppercase, 0.75rem, grey */
.accounts-table tbody td  /* 0.9rem, vertical-align: middle */
.account-link     /* fw-500, color:inherit, underline on hover */
.row-count        /* 0.8rem grey footer "N Einträge" */
```

### Page structure
```html
<div class="page-header d-flex justify-content-between align-items-center">
  <h2 class="mb-0">Titel</h2>
  <!-- optional action buttons -->
</div>

<div class="filter-card">
  <form method="get">
    <div class="row g-2 align-items-end">
      <div class="col-md-3">
        <label class="form-label">Suche</label>
        <input type="text" name="q" class="form-control form-control-sm">
      </div>
      <div class="col-md-auto">
        <button type="submit" class="btn btn-primary btn-sm">Filtern</button>
        <a href="..." class="btn btn-outline-secondary btn-sm">Zurücksetzen</a>
      </div>
    </div>
  </form>
</div>

<div class="table-responsive accounts-table">
  <table class="table table-hover mb-0">
    <thead><tr><th>...</th></tr></thead>
    <tbody>
      {% for item in items %}
      <tr><td>...</td></tr>
      {% empty %}
      <tr><td colspan="N" class="text-center text-muted py-4">Keine Einträge.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>
<p class="row-count">{{ items|length }} Einträge</p>
```

## Workflow

- **Always work on a feature branch** and open a PR — never commit directly to `master`
- **After opening a PR**, immediately run a code review (`/code-review`) on it

## Versioning & Release Notes

- **Schema**: CalVer `YYYY.N` (year + sequential number), e.g. `2026.1`, `2026.4`
- **Source of truth**: `version` field in `pyproject.toml`
- **Displayed in**: Sidebar via `core.context_processors.app_version`
- **On every PR**: Bump version in `pyproject.toml` and add a new section to `CHANGELOG.md`
- **Multiple PRs before release**: All changes go into the same version block until a release is made
- **CHANGELOG format**:
  ```markdown
  ## YYYY.N
  ### Verbesserungen / Fehlerbehebungen / Neue Features
  - Beschreibung der Änderung
  ```
