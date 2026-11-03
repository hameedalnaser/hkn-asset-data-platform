#!/usr/bin/env bash
# =============================================================================
# azure_provision_sql.sh
# Provision a cost-controlled Azure SQL Database for the HKN asset demo.
#
# Budget note ($200 credit): we use the SERVERLESS General Purpose tier with
# AUTO-PAUSE after 1 hour idle. When paused you pay only for storage
# (a few cents/day). A day of light dev typically costs well under $1.
#
# Run it line by line the first time so you see each step, or `bash` the whole
# file. It is idempotent-ish: re-running create commands on existing resources
# will error harmlessly; comment out what already exists.
#
# PREREQUISITE: `az login` (run it yourself: `! az login`).
# =============================================================================
set -euo pipefail

# ---- edit these ----
RG="hkn-asset-rg"                 # resource group
LOCATION="westeurope"             # pick one near you; affects latency not cost much
SQL_SERVER="hkn-asset-sql-$RANDOM" # must be globally unique
SQL_DB="hkn_asset"
ADMIN_USER="hkn_admin"
# Admin password: DO NOT hardcode. Export it before running:
#   ! export SQL_ADMIN_PASSWORD='YourStrong!Passw0rd'
ADMIN_PASS="${SQL_ADMIN_PASSWORD:?Set SQL_ADMIN_PASSWORD env var first}"

echo "Using server name: $SQL_SERVER  (save this — it goes in .env)"

# ---- resource group ----
az group create --name "$RG" --location "$LOCATION"

# ---- logical SQL server ----
az sql server create \
  --name "$SQL_SERVER" \
  --resource-group "$RG" \
  --location "$LOCATION" \
  --admin-user "$ADMIN_USER" \
  --admin-password "$ADMIN_PASS"

# ---- firewall: allow Azure services + your current IP only ----
# Least exposure: not open to the world. Re-run the client-IP rule if your IP changes.
MY_IP="$(curl -s https://api.ipify.org)"
az sql server firewall-rule create \
  --resource-group "$RG" --server "$SQL_SERVER" \
  --name "AllowMyClientIP" --start-ip-address "$MY_IP" --end-ip-address "$MY_IP"

# Allow Azure-internal services (needed later so App Service can reach the DB).
az sql server firewall-rule create \
  --resource-group "$RG" --server "$SQL_SERVER" \
  --name "AllowAzureServices" --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0

# ---- the database: SERVERLESS, auto-pause, small (cheap) ----
az sql db create \
  --resource-group "$RG" --server "$SQL_SERVER" --name "$SQL_DB" \
  --edition GeneralPurpose \
  --compute-model Serverless \
  --family Gen5 \
  --capacity 1 \
  --min-capacity 0.5 \
  --auto-pause-delay 60 \
  --backup-storage-redundancy Local \
  --zone-redundant false

echo
echo "=== DONE. Put these in your .env ==="
echo "SQL_SERVER=$SQL_SERVER.database.windows.net"
echo "SQL_DATABASE=$SQL_DB"
echo "SQL_USERNAME=$ADMIN_USER     # admin — only for migrations; app uses etl_user/api_user"
echo "SQL_PASSWORD=<the password you exported>"
echo "SQL_DRIVER=ODBC Driver 18 for SQL Server"
echo
echo "To avoid surprise cost, you can pause/delete later with:"
echo "  az sql db delete -g $RG -s $SQL_SERVER -n $SQL_DB --yes   # or"
echo "  az group delete -n $RG --yes   # removes everything"
