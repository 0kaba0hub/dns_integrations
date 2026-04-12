#!/usr/bin/env python3
"""
CyberPanel integration for secondary DNS service.

Modes:
  add <domain>       — Register domain as secondary zone
  remove <domain>    — Remove domain from secondary DNS
  sync               — Sync all CyberPanel domains with secondary DNS
  list               — List zones on secondary DNS

Configuration via /etc/seconddns.conf or environment variables:
  SECONDDNS_API_URL  — API base URL (e.g. https://seconddns.com)
  SECONDDNS_API_KEY  — API key from dashboard
  SECONDDNS_MASTER_IP — Primary DNS server IP (auto-detected if not set)
"""

import json
import os
import sys
import socket
import subprocess
import urllib.request
import urllib.error
import configparser

CONFIG_FILE = "/etc/seconddns.conf"

def load_config():
    config = {}

    # Load from config file
    if os.path.exists(CONFIG_FILE):
        cp = configparser.ConfigParser()
        cp.read(CONFIG_FILE)
        if cp.has_section("seconddns"):
            config["api_url"] = cp.get("seconddns", "api_url", fallback="")
            config["api_key"] = cp.get("seconddns", "api_key", fallback="")
            config["master_ip"] = cp.get("seconddns", "master_ip", fallback="")

    # Environment overrides
    config["api_url"] = os.environ.get("SECONDDNS_API_URL", config.get("api_url", "")).rstrip("/")
    config["api_key"] = os.environ.get("SECONDDNS_API_KEY", config.get("api_key", ""))
    config["master_ip"] = os.environ.get("SECONDDNS_MASTER_IP", config.get("master_ip", ""))

    if not config["api_url"] or not config["api_key"]:
        print("Error: SECONDDNS_API_URL and SECONDDNS_API_KEY are required.", file=sys.stderr)
        print(f"Set them in {CONFIG_FILE} or as environment variables.", file=sys.stderr)
        sys.exit(1)

    # Auto-detect master IP if not set
    if not config["master_ip"]:
        config["master_ip"] = detect_master_ip()

    return config


def detect_master_ip():
    """Detect the server's public IPv4 address."""
    try:
        resp = urllib.request.urlopen("https://api.ipify.org", timeout=5)
        return resp.read().decode().strip()
    except Exception:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            print("Error: Could not detect master IP. Set SECONDDNS_MASTER_IP.", file=sys.stderr)
            sys.exit(1)


def api_request(config, method, path, data=None):
    """Make an API request to the secondary DNS service."""
    url = f"{config['api_url']}{path}"
    headers = {
        "X-API-Key": config["api_key"],
        "Content-Type": "application/json",
    }
    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        resp = urllib.request.urlopen(req, timeout=15)
        return json.loads(resp.read().decode()) if resp.status != 204 else None
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_data = json.loads(error_body)
        except Exception:
            error_data = {"error": error_body}
        return {"_status": e.code, **error_data}


def list_zones(config):
    """List all zones on the secondary DNS service."""
    result = api_request(config, "GET", "/api/zones")
    if isinstance(result, list):
        return result
    print(f"Error listing zones: {result}", file=sys.stderr)
    return []


def add_zone(config, domain):
    """Add a domain to the secondary DNS service."""
    domain = domain.lower().rstrip(".")
    print(f"Adding zone: {domain} (master: {config['master_ip']})")
    result = api_request(config, "POST", "/api/zones", {
        "name": domain,
        "masterIp": config["master_ip"],
    })
    if result and result.get("_status"):
        status = result["_status"]
        error = result.get("error", "Unknown error")
        if status == 409:
            print(f"  Zone {domain} already exists, skipping.")
        elif status == 403:
            print(f"  Error: {error} (zone limit reached?)", file=sys.stderr)
        else:
            print(f"  Error ({status}): {error}", file=sys.stderr)
        return False
    print(f"  Zone {domain} added successfully.")
    return True


def remove_zone(config, domain):
    """Remove a domain from the secondary DNS service."""
    domain = domain.lower().rstrip(".")
    zones = list_zones(config)
    zone = next((z for z in zones if z["name"].rstrip(".") == domain), None)
    if not zone:
        print(f"  Zone {domain} not found on secondary DNS.")
        return False
    print(f"Removing zone: {domain}")
    result = api_request(config, "DELETE", f"/api/zones/{zone['id']}")
    if result and result.get("_status"):
        print(f"  Error: {result.get('error', 'Unknown')}", file=sys.stderr)
        return False
    print(f"  Zone {domain} removed successfully.")
    return True


def get_cyberpanel_domains():
    """Get list of domains from CyberPanel."""
    domains = []

    # Method 1: CyberPanel CLI
    try:
        result = subprocess.run(
            ["cyberpanel", "listWebsitesJson"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            if isinstance(data, list):
                for site in data:
                    name = site.get("domain") or site.get("domainName")
                    if name:
                        domains.append(name.lower().rstrip("."))
                return domains
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass

    # Method 2: Read from CyberPanel database
    try:
        result = subprocess.run(
            ["sqlite3", "/usr/local/CyberCP/database.sqlite3",
             "SELECT domain FROM websiteFunctions_websites;"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if line.strip():
                    domains.append(line.strip().lower().rstrip("."))
            return domains
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Method 3: Read from named/PowerDNS zone files
    zone_dir = "/etc/namedb"
    if os.path.isdir(zone_dir):
        for f in os.listdir(zone_dir):
            if f.endswith(".db"):
                domains.append(f[:-3].lower())

    return domains


def sync(config):
    """Sync CyberPanel domains with secondary DNS service."""
    local_domains = set(get_cyberpanel_domains())
    remote_zones = list_zones(config)
    remote_domains = {z["name"].rstrip("."): z for z in remote_zones}

    print(f"Local domains: {len(local_domains)}")
    print(f"Remote zones:  {len(remote_domains)}")

    # Add missing
    added = 0
    for domain in sorted(local_domains - set(remote_domains.keys())):
        if add_zone(config, domain):
            added += 1

    # Remove stale
    removed = 0
    for domain in sorted(set(remote_domains.keys()) - local_domains):
        if remove_zone(config, domain):
            removed += 1

    print(f"\nSync complete: +{added} added, -{removed} removed")


def cmd_list(config):
    """Print zones on secondary DNS."""
    zones = list_zones(config)
    if not zones:
        print("No zones found.")
        return
    print(f"{'Name':<40} {'Status':<10} {'Master IP':<18} {'Last Sync'}")
    print("-" * 90)
    for z in zones:
        print(f"{z['name']:<40} {z.get('status','?'):<10} {z.get('masterIp','?'):<18} {z.get('lastSync','never')}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    config = load_config()

    if cmd == "add" and len(sys.argv) >= 3:
        add_zone(config, sys.argv[2])
    elif cmd == "remove" and len(sys.argv) >= 3:
        remove_zone(config, sys.argv[2])
    elif cmd == "sync":
        sync(config)
    elif cmd == "list":
        cmd_list(config)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
