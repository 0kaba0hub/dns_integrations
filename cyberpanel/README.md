# CyberPanel Integration

Automatic secondary DNS zone management for CyberPanel servers.

## Features

- Auto-add zones when domains are created in CyberPanel
- Auto-remove zones when domains are deleted
- Periodic sync (cron) to catch any missed changes
- Manual CLI for add/remove/sync/list
- Auto-detects server public IP as master

## Quick Install

```bash
git clone https://github.com/0kaba0hub/dns_integrations.git
cd dns_integrations/cyberpanel
sudo bash install.sh
```

Then edit `/etc/seconddns.conf`:

```ini
[seconddns]
api_url = https://seconddns.com
api_key = YOUR_API_KEY_HERE
master_ip =
```

## Usage

```bash
# Sync all existing domains
seconddns sync

# List zones on secondary DNS
seconddns list

# Manually add a domain
seconddns add example.com

# Manually remove a domain
seconddns remove example.com
```

## What Gets Installed

| File | Purpose |
|---|---|
| `/usr/local/bin/seconddns` | Main CLI script |
| `/etc/seconddns.conf` | Configuration (API key, URL) |
| `/etc/cron.d/seconddns-sync` | Periodic sync every 6 hours |
| `/usr/local/CyberCP/hooks/post_domain_create.sh` | Auto-add hook |
| `/usr/local/CyberCP/hooks/post_domain_delete.sh` | Auto-remove hook |

## Logs

```bash
tail -f /var/log/seconddns.log
```

## Uninstall

```bash
sudo rm /usr/local/bin/seconddns
sudo rm /etc/cron.d/seconddns-sync
sudo rm /usr/local/CyberCP/hooks/post_domain_create.sh
sudo rm /usr/local/CyberCP/hooks/post_domain_delete.sh
# Optionally: sudo rm /etc/seconddns.conf
```

## Requirements

- Python 3.6+
- CyberPanel installed
- Network access to secondary DNS API
- Primary DNS (BIND/PowerDNS) configured to allow AXFR from secondary DNS server IP
