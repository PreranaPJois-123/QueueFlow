# AWS EC2 deployment (Docker Compose)

Single EC2 instance running the existing Compose stack. Only the frontend nginx
container is public; it serves the SPA and proxies `/api` (HTTP + WebSockets),
`/docs` and `/openapi.json` to the backend over the private Compose network.

```
Internet ──80──▶ frontend (nginx) ──/api──▶ backend (FastAPI) ──▶ postgres (volume)
                                                         └──────▶ redis
          (postgres 5432, redis 6379, backend 8000 bind to 127.0.0.1 only)
```

## Cost (check your own account before launching)

Billable items: instance hours, EBS storage, the public IPv4 address
($0.005/hour, including Elastic IPs, under AWS's 2024 IPv4 pricing), and data
transfer. Accounts created on or after 15 July 2025 use the credit-based
Free Tier (up to $200 credits, free plan for 6 months); older accounts use the
legacy 12-month tier. Pick an instance the launch wizard labels **Free tier
eligible** for *your* account, and create an AWS Budgets alert first.

Recommended: `t3.small` (2 GiB). A 1 GiB instance (`t3.micro`) works only with
the swap file below, because building the images (`npm ci`, Vite, pip) is
memory-heavy.

## 1. Launch the instance (AWS console)

- Region: closest to users (e.g. `ap-south-1`, Mumbai).
- AMI: **Ubuntu Server 24.04 LTS** (x86_64). Storage: 20 GiB gp3.
- Key pair: create/download one; never commit it.
- Security group, inbound rules only:
  - SSH `22` from **My IP** only
  - HTTP `80` from `0.0.0.0/0` (and `::/0` if using IPv6)
  - Nothing else. Do **not** open 5432, 6379 or 8000.
- Allocate an **Elastic IP** and associate it. The public IP is compiled into
  the frontend bundle (`VITE_API_URL`), so a changing IP would require a rebuild.

## 2. Install Docker (official Docker apt repository)

```sh
ssh -i KEY.pem ubuntu@ELASTIC_IP
sudo apt-get update && sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list
sudo apt-get update && sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker ubuntu && exit   # reconnect so the group applies

# 2 GiB swap (required on 1 GiB instances, harmless otherwise)
sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

## 3. Configure and start

```sh
git clone https://github.com/PreranaPJois-123/QueueFlow.git && cd QueueFlow
cp .env.example .env && chmod 600 .env
sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$(openssl rand -hex 32)/; s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 24)/" .env
nano .env   # set the values below
```

```
VITE_API_URL=http://ELASTIC_IP
CORS_ORIGINS=http://ELASTIC_IP
FRONTEND_PORT=80
INITIAL_ADMIN_EMAIL=you@example.com
INITIAL_ADMIN_NAME=Your Name
INITIAL_ADMIN_PASSWORD=<strong password, typed here only>
```

```sh
docker compose up -d --build
docker compose ps                    # all four services "healthy"/"running"
curl -s http://localhost/api/health  # {"status":"healthy",...,"database":"up","redis":"up"}
```

Then remove `INITIAL_ADMIN_PASSWORD` from `.env` and run `docker compose up -d`
(startup provisioning only runs when no admin exists; it never resets one).
More staff: `docker compose exec backend python -m app.provision_user --email E --name 'N' --role STAFF`.

## 4. Verify from your own computer

```sh
curl -s http://ELASTIC_IP/api/health
QF_ADMIN_EMAIL=you@example.com QF_ADMIN_PASSWORD='...' python3 scripts/smoke_test.py http://ELASTIC_IP
nc -vz -w 5 ELASTIC_IP 5432; nc -vz -w 5 ELASTIC_IP 6379; nc -vz -w 5 ELASTIC_IP 8000   # all must fail
```

Open `http://ELASTIC_IP` in a browser: register a customer, join a queue, and
call/serve it from the staff account in a second browser to see live updates.

Reboot test: `sudo reboot`, wait, then re-run the health check. Containers use
`restart: unless-stopped` and Docker is enabled at boot. Data lives in the
`postgres_data` named volume and survives restarts and `docker compose down`
(**not** `docker compose down -v`, which deletes it).

## 5. Backups

```sh
chmod +x scripts/backup_db.sh && ./scripts/backup_db.sh      # writes ./backups/*.sql.gz, keeps 7
( crontab -l 2>/dev/null; echo "0 2 * * * cd $HOME/QueueFlow && ./scripts/backup_db.sh >> backups/cron.log 2>&1" ) | crontab -
scp -i KEY.pem ubuntu@ELASTIC_IP:QueueFlow/backups/*.sql.gz .  # copy off-instance
```

Dumps on the same disk do not protect against losing the instance; copy them
off regularly (EBS snapshots are an option but are billed).

## Limits and teardown

- **HTTP only.** No domain or TLS is configured, so credentials travel
  unencrypted; treat this as a demo deployment until HTTPS is added.
- One backend process (the in-memory WebSocket manager requires it).
- Updating: `git pull && docker compose up -d --build`.
- To stop all charges: terminate the instance, delete its EBS volume if
  retained, and **release the Elastic IP** (an unattached EIP is still billed).
