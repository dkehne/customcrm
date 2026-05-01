# CustomCRM

German-language Django CRM for municipal customer management. Manages accounts (Kommunen), contacts, products with workflow phases, contracts with auto-renewal logic, marketing campaigns, and inbound email processing.

## Features

### Account Management
- **Accounts** with type classification, German federal state (Bundesland), hierarchical parent-child relationships, and owner assignment
- **Contacts** per account with primary contact flag, email, phone, gender, and position
- **Activity log** tracking calls, emails, meetings, and completed tasks
- **Todo list** with due dates and PDF attachments

### Products & Workflow
- **Products** with configurable workflow phases (ordered stages with a final phase marker)
- **Dynamic fields** per product — date, integer, and boolean field types
- **Account-Product assignments** tracking current workflow phase and field values

### Contracts
- **Contract types** for classification
- **Contracts** with gross annual price, start date, duration, and document uploads (PDF)
- **Auto-renewal logic**: contracts extend by `renewal_interval_months` until past today, unless marked as self-cancelling
- **Notice period** tracking (default: 3 months)

### Campaigns
- **Marketing campaigns** with date ranges
- **Denormalized contact snapshots** preserving contact data at the time of campaign addition, independent of later edits

### Email Integration
- **Profile page** where users manage their sender email addresses and view their personal BCC address for email capture
- **Inbound email processing** via IMAP (`fetch_emails` management command)
  - Automatic user matching via BCC token or sender email address
  - Automatic account matching via recipient/sender email against contact records
  - Deduplication by SMTP Message-ID
  - Original `.eml` file and attachment storage
- **Unresolved email queue** for manually assigning emails that couldn't be matched to an account
- **Collapsible email details** in the account activity timeline — sender/recipient info, plain-text body, attachment downloads, and original `.eml` download

### User Roles & Access Control
- **Superuser**: Full access to all accounts, contracts, settings (account types, products, contract types, user management), and global statistics dashboard
- **Verwalter** (default): Sees only owned accounts, filtered dashboard with upcoming todos

## Architecture

```
core/                   Django project config, authentication, user model, dashboards
accounts/               Accounts, contacts, activities, todos
products/               Products with dynamic phases and custom fields
contracts/              Contracts with documents and auto-renewal
campaigns/              Marketing campaigns with contact snapshots
emails/                 Email integration, profile, inbound processing
templates/              Global templates (base layout, per-app templates)
media/                  Uploaded files (contract docs, email attachments, .eml files)
```

### Key Model Relationships

```
Account
├── Contacts (one-to-many, primary contact flag)
├── AccountProducts → Product (with current_phase → ProductPhase)
│   └── AccountProductFieldValues → ProductField (dynamic fields)
├── Contracts → ContractType, ContractDocuments
├── Activities → optional InboundEmail
│                  └── EmailAttachments
├── Todos
└── InboundEmails

CustomUser
├── UserEmailAddress (registered sender addresses)
├── UserInboundAddress (system-generated BCC address, 1:1)
└── InboundEmails (processed incoming mail)

Campaign
└── CampaignContacts (denormalized contact snapshots)
```

### Common Patterns
- **Soft delete**: `is_archived` boolean on most models — archive before permanent deletion
- **Owner filtering**: Non-superusers see only `account__owner=request.user`
- **Permission checks**: Superadmin-only views redirect with error message for Verwalter users
- **CSV export**: Semi-colon delimiter, UTF-8-sig encoding

## Setup

### Requirements

- Python 3.12+
- Django 6.0+

### Installation

```bash
# Clone and enter the project
git clone <repo-url> && cd customcrm

# Create virtual environment and install dependencies
python -m venv venv
source venv/bin/activate
pip install -e .

# Run migrations (includes seed data for the "Integreat" product)
python manage.py migrate

# Create a superuser
python manage.py createsuperuser

# Start the development server
python manage.py runserver
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection URL (e.g. `postgres://user:pass@host:5432/dbname`) | SQLite |
| `OIDC_ENABLED` | Enable OpenID Connect authentication | `False` |
| `OIDC_RP_CLIENT_ID` | OIDC client ID | — |
| `OIDC_RP_CLIENT_SECRET` | OIDC client secret | — |
| `OIDC_RP_SIGN_ALGO` | OIDC signing algorithm | `RS256` |
| `OIDC_OP_AUTHORIZATION_ENDPOINT` | OIDC authorization URL | — |
| `OIDC_OP_TOKEN_ENDPOINT` | OIDC token URL | — |
| `OIDC_OP_USER_ENDPOINT` | OIDC userinfo URL | — |
| `OIDC_OP_JWKS_ENDPOINT` | OIDC JWKS URL | — |
| `INBOUND_EMAIL_DOMAIN` | Domain for generated BCC addresses | `example.com` |
| `IMAP_HOST` | IMAP server hostname | — |
| `IMAP_PORT` | IMAP server port | `993` |
| `IMAP_USER` | IMAP login username | — |
| `IMAP_PASSWORD` | IMAP login password | — |
| `IMAP_USE_SSL` | Use SSL for IMAP connection | `True` |

### Database

SQLite by default (`db.sqlite3`). For PostgreSQL, set the `DATABASE_URL` environment variable and install the driver:

```bash
pip install -e ".[postgres]"
export DATABASE_URL=postgres://user:password@localhost:5432/customcrm
python manage.py migrate
```

### Email Integration Setup

1. Set `INBOUND_EMAIL_DOMAIN` to the domain your mail server accepts (e.g. `crm.example.com`)
2. Configure your mail server to accept catch-all mail for that domain and deliver it to a single IMAP mailbox
3. Set the `IMAP_*` environment variables to point to that mailbox
4. Users register their sender email addresses on the profile page and use the displayed BCC address when sending emails
5. Run the fetch command continuously using the built-in daemon mode:
   ```bash
   # Run as a daemon, polling every 5 minutes (default)
   python manage.py fetch_emails --daemon

   # Custom interval (e.g. every 2 minutes)
   python manage.py fetch_emails --daemon --interval 120
   ```
   The daemon handles SIGINT/SIGTERM for clean shutdown. For production, run it as a **systemd service** (see below).
6. Emails that can't be automatically matched to an account appear under "Nicht aufgeloeste E-Mails" for manual assignment

### Authentication with Keycloak or Other OIDC Providers

The CRM supports OpenID Connect via [mozilla-django-oidc](https://mozilla-django-oidc.readthedocs.io/). This allows integration with identity providers like **Keycloak**, Auth0, Azure AD, or any OIDC-compliant service.

**Keycloak example:**

1. Create a client in your Keycloak realm with:
   - Client Protocol: `openid-connect`
   - Access Type: `confidential`
   - Valid Redirect URIs: `https://your-crm-domain/oidc/callback/`
2. Set the environment variables:
   ```bash
   export OIDC_ENABLED=True
   export OIDC_RP_CLIENT_ID=customcrm
   export OIDC_RP_CLIENT_SECRET=your-client-secret
   export OIDC_OP_AUTHORIZATION_ENDPOINT=https://keycloak.example.com/realms/your-realm/protocol/openid-connect/auth
   export OIDC_OP_TOKEN_ENDPOINT=https://keycloak.example.com/realms/your-realm/protocol/openid-connect/token
   export OIDC_OP_USER_ENDPOINT=https://keycloak.example.com/realms/your-realm/protocol/openid-connect/userinfo
   export OIDC_OP_JWKS_ENDPOINT=https://keycloak.example.com/realms/your-realm/protocol/openid-connect/certs
   ```
3. **Role mapping**: The CRM reads `realm_access.roles` from JWT claims. If the role `superuser` is present, the user gets Superuser access; otherwise they are assigned the Verwalter role. Configure a corresponding role in your Keycloak realm and assign it to admin users.
4. User accounts are created automatically on first OIDC login and updated on subsequent logins (username, email, first/last name synced from claims).

For other OIDC providers, adapt the endpoint URLs accordingly. The custom backend (`core/backends.py`) maps `preferred_username`, `email`, `given_name`, and `family_name` claims to user fields.

## Management Commands

| Command | Description |
|---|---|
| `python manage.py runserver` | Start development server |
| `python manage.py migrate` | Apply database migrations |
| `python manage.py import_csv` | Import accounts/contacts from CSV |
| `python manage.py fetch_emails` | Fetch and process inbound emails via IMAP (single run) |
| `python manage.py fetch_emails --daemon` | Run as a continuous polling daemon (default: every 5 min) |
| `python manage.py fetch_emails --daemon --interval N` | Daemon mode with custom interval in seconds |
| `python manage.py fetch_emails --dry-run` | Preview email processing without saving |
| `python manage.py test` | Run tests |

### Email Daemon with systemd

To run the email fetcher as a persistent background service:

1. Create `/etc/systemd/system/customcrm-emails.service`:
   ```ini
   [Unit]
   Description=CustomCRM Email Fetcher
   After=network.target

   [Service]
   Type=simple
   User=www-data
   WorkingDirectory=/path/to/customcrm
   ExecStart=/path/to/customcrm/venv/bin/python manage.py fetch_emails --daemon --interval 300
   Restart=on-failure
   RestartSec=30

   [Install]
   WantedBy=multi-user.target
   ```

2. Enable and start:
   ```bash
   sudo systemctl enable customcrm-emails
   sudo systemctl start customcrm-emails
   ```

3. Check status / logs:
   ```bash
   sudo systemctl status customcrm-emails
   sudo journalctl -u customcrm-emails -f
   ```

## Production Considerations

- Replace `SECRET_KEY` with a securely generated value
- Set `DEBUG = False` and configure `ALLOWED_HOSTS`
- Use PostgreSQL or another production-grade database
- Serve static/media files via a web server (nginx) or object storage
- Use a WSGI server like gunicorn behind a reverse proxy
- Store sensitive settings (`SECRET_KEY`, `IMAP_PASSWORD`, `OIDC_RP_CLIENT_SECRET`) in environment variables or a secrets manager
- Configure HTTPS and update `CSRF_TRUSTED_ORIGINS` accordingly
- Set up log rotation for the `fetch_emails` cron job
