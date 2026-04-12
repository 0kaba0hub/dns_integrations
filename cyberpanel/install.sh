#!/bin/bash
set -e

INSTALL_DIR="/usr/local/bin"
CONFIG_FILE="/etc/seconddns.conf"
HOOK_DIR="/usr/local/CyberCP/postfixSenderPolicy"
CRON_FILE="/etc/cron.d/seconddns-sync"

echo "=== SecondDNS CyberPanel Integration Installer ==="
echo ""

# Copy main script
cp seconddns.py "$INSTALL_DIR/seconddns"
chmod +x "$INSTALL_DIR/seconddns"
echo "[+] Installed seconddns to $INSTALL_DIR/seconddns"

# Config
if [ ! -f "$CONFIG_FILE" ]; then
    cp seconddns.conf.example "$CONFIG_FILE"
    chmod 600 "$CONFIG_FILE"
    echo "[+] Created config at $CONFIG_FILE"
    echo "    → Edit $CONFIG_FILE and set your api_url and api_key"
else
    echo "[=] Config already exists at $CONFIG_FILE, skipping"
fi

# CyberPanel post-create hook
if [ -d "/usr/local/CyberCP" ]; then
    mkdir -p /usr/local/CyberCP/hooks
    cat > /usr/local/CyberCP/hooks/post_domain_create.sh << 'HOOK'
#!/bin/bash
# Called by CyberPanel after domain creation
# $1 = domain name
if [ -x /usr/local/bin/seconddns ]; then
    /usr/local/bin/seconddns add "$1" >> /var/log/seconddns.log 2>&1 &
fi
HOOK
    chmod +x /usr/local/CyberCP/hooks/post_domain_create.sh

    cat > /usr/local/CyberCP/hooks/post_domain_delete.sh << 'HOOK'
#!/bin/bash
# Called by CyberPanel after domain deletion
# $1 = domain name
if [ -x /usr/local/bin/seconddns ]; then
    /usr/local/bin/seconddns remove "$1" >> /var/log/seconddns.log 2>&1 &
fi
HOOK
    chmod +x /usr/local/CyberCP/hooks/post_domain_delete.sh
    echo "[+] Installed CyberPanel hooks"
fi

# Cron job for periodic sync (every 6 hours)
cat > "$CRON_FILE" << 'CRON'
# Sync CyberPanel domains with secondary DNS service
0 */6 * * * root /usr/local/bin/seconddns sync >> /var/log/seconddns.log 2>&1
CRON
chmod 644 "$CRON_FILE"
echo "[+] Installed cron job (sync every 6 hours)"

echo ""
echo "=== Installation complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit $CONFIG_FILE — set your api_url and api_key"
echo "  2. Run: seconddns sync — to sync existing domains"
echo "  3. Run: seconddns list — to verify zones"
echo ""
echo "Logs: /var/log/seconddns.log"
