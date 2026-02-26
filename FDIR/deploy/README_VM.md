# VM Deployment (systemd + nginx + SSL)

This deploys the backend on a Linux VM with:

- `systemd` to run Gunicorn
- `nginx` as reverse proxy (supports WebSockets)
- TLS via `certbot`

## 1) VM prerequisites

Ubuntu/Debian example:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip nginx
```

Open firewall ports:

- 80/tcp (HTTP)
- 443/tcp (HTTPS)

## 2) Create a service user

```bash
sudo useradd --system --create-home --shell /usr/sbin/nologin fdir
```

## 3) Deploy the code

Recommended layout:

- `/opt/fdir/FDIR`  (this folder from the repo)
- `/opt/fdir/venv`  (python venv)

```bash
sudo mkdir -p /opt/fdir
sudo chown -R fdir:fdir /opt/fdir
```

Copy your `FDIR/` folder into `/opt/fdir/FDIR` (git clone or scp).

## 4) Python env + dependencies

```bash
sudo -u fdir python3 -m venv /opt/fdir/venv
sudo -u fdir /opt/fdir/venv/bin/pip install -r /opt/fdir/FDIR/requirements.txt
```

## 5) Configure systemd

1) Copy the unit file:

```bash
sudo cp /opt/fdir/FDIR/deploy/systemd/fdir-backend.service /etc/systemd/system/fdir-backend.service
```

2) Edit paths + domains:

```bash
sudo nano /etc/systemd/system/fdir-backend.service
```

You must set:

- `WorkingDirectory=/opt/fdir/FDIR`
- `ExecStart=/opt/fdir/venv/bin/gunicorn -c backend/gunicorn_conf.py backend.api:app`
- `FDIR_ALLOW_ORIGINS=https://YOUR_FRONTEND_DOMAIN`

Recommended production settings:

- `FDIR_SIMULATION=0`
- `WEB_CONCURRENCY=1` (SQLite-safe)

3) Start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now fdir-backend
sudo systemctl status fdir-backend --no-pager
```

Logs:

```bash
journalctl -u fdir-backend -f
```

## 6) Configure nginx reverse proxy

```bash
sudo cp /opt/fdir/FDIR/deploy/nginx/fdir-backend.conf /etc/nginx/sites-available/fdir-backend
sudo ln -sf /etc/nginx/sites-available/fdir-backend /etc/nginx/sites-enabled/fdir-backend
sudo nginx -t
sudo systemctl reload nginx
```

Now you should be able to hit:

- `http://api.YOUR_DOMAIN/healthz`

## 7) Enable SSL (certbot)

```bash
sudo apt-get install -y certbot python3-certbot-nginx
sudo certbot --nginx -d api.YOUR_DOMAIN
```

Verify:

- `https://api.YOUR_DOMAIN/healthz`
- `https://api.YOUR_DOMAIN/docs`

## Common pitfalls

- WebSockets require the nginx `Upgrade` / `Connection` headers (already in the template).
- If you set `WEB_CONCURRENCY>1`, the backend will disable simulation automatically.
- If the frontend is on a different domain, set `FDIR_ALLOW_ORIGINS` exactly (no trailing slash).
