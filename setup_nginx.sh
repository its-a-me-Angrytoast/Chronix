#!/bin/bash
set -e

echo "Detected Arch Linux."
echo "Installing Nginx..."
pacman -S --noconfirm nginx

echo "Configuring Nginx directories..."
mkdir -p /etc/nginx/sites-available
mkdir -p /etc/nginx/sites-enabled

# Backup config
if [ ! -f /etc/nginx/nginx.conf.bak ]; then
    cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.bak
fi

# Ensure include sites-enabled is present in nginx.conf
if ! grep -q "sites-enabled" /etc/nginx/nginx.conf; then
    # Basic injection into http block - looking for the end of the http block is safer
    # But simplified for Arch default config which usually ends http block with }
    sed -i '/http {/a \    include /etc/nginx/sites-enabled/*;' /etc/nginx/nginx.conf
    echo "Updated /etc/nginx/nginx.conf to include sites-enabled."
fi

echo "Creating Chronix Dashboard configuration..."
cat > /etc/nginx/sites-available/chronix <<EOF
server {
    listen 80;
    server_name localhost;

    location / {
        proxy_pass http://127.0.0.1:9091;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_cache_bypass \$http_upgrade;
    }
}
EOF

# Enable the site
ln -sf /etc/nginx/sites-available/chronix /etc/nginx/sites-enabled/chronix

echo "Testing Nginx configuration..."
nginx -t

echo "Starting Nginx service..."
systemctl enable --now nginx
systemctl restart nginx

echo "Nginx setup complete! Dashboard should be available at http://localhost"
