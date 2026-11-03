# Step 4 runbook — provision Azure SQL and load end to end

Everything you run yourself is marked **▶ run**. Commands prefixed `!` are meant
to be typed into the Claude Code prompt so the output is captured.

## 0. One-time local prerequisites

**▶ run** — Azure CLI + Microsoft ODBC driver (pulls in unixodbc):
```
! brew update && brew install azure-cli
! brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release && HOMEBREW_ACCEPT_EULA=Y brew install msodbcsql18 mssql-tools18
```
`pyodbc` is already in the venv; it starts working once the driver above is installed.

## 1. Log in to Azure

**▶ run:**
```
! az login
```
If you have more than one subscription:
```
! az account set --subscription "<your subscription name or id>"
```

## 2. Provision the database (serverless, auto-pause — protects your $200)

Set a strong admin password in the environment (never in a file):
```
! export SQL_ADMIN_PASSWORD='Choose-A-Strong-One!2026'
! bash scripts/azure_provision_sql.sh
```
The script prints the server name and the exact `.env` values at the end. **Copy them.**

## 3. Point the app at the DB (admin creds, for migrations only)

Create `.env` from the template and fill in what the script printed:
```
cp .env.example .env
# edit .env: SQL_SERVER, SQL_DATABASE, SQL_USERNAME=hkn_admin, SQL_PASSWORD=<the one you exported>
```

## 4. Apply the schema + security migrations

**▶ run** (admin login creates schemas, roles, procs):
```
PYTHONPATH=src .venv/bin/python scripts/run_migrations.py
```
This runs `sql/01` and `03`–`09`. It intentionally skips `02` (user creation)
because that needs real passwords — do that next.

## 5. Create the two app users (least privilege)

```
cp sql/02_create_users.sql.template sql/02_create_users.sql
# edit sql/02_create_users.sql: replace __ETL_PASSWORD__ and __API_PASSWORD__
PYTHONPATH=src .venv/bin/python scripts/run_migrations.py --only 02_create_users
```
(`sql/02_create_users.sql` is gitignored, so the passwords never get committed.)

## 6. Switch .env to the low-privilege ETL user

The pipeline should NOT run as admin. Edit `.env`:
```
SQL_USERNAME=etl_user
SQL_PASSWORD=<the ETL password you just set>
```

## 7. Generate reports and load them

```
PYTHONPATH=src .venv/bin/python scripts/generate_sample_reports.py --days 30
PYTHONPATH=src .venv/bin/python scripts/run_ingestion.py
```

## 8. Verify

```
PYTHONPATH=src .venv/bin/python scripts/verify_load.py
```
You should see row counts in every fact, a populated `audit.load_batch`, and
any reconciliation flags. **This is the end-to-end proof the pipeline works.**

## Cost hygiene

When you stop for the day the DB auto-pauses after 1h idle (storage-only cost).
To stop paying entirely between sessions:
```
! az sql db delete  -g hkn-asset-rg -s <your-server> -n hkn_asset --yes   # keep server
! az group delete   -n hkn-asset-rg --yes                                  # nuke everything
```
Re-running the runbook rebuilds it in minutes.
