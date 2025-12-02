#!/bin/bash
set -e

echo "Updating Nginx configuration for chronix.work.gd..."

# Copy the local config to the Nginx sites-available directory
sudo cp nginx_chronix.conf /etc/nginx/sites-available/chronix

# Ensure the symbolic link exists
if [ ! -L /etc/nginx/sites-enabled/chronix ]; then
    echo "Creating symlink..."
    sudo ln -s /etc/nginx/sites-available/chronix /etc/nginx/sites-enabled/chronix
fi

echo "Testing Nginx configuration..."
if sudo nginx -t; then
    echo "Configuration valid. Restarting Nginx..."
    sudo systemctl restart nginx
    echo "Nginx restarted successfully."
    echo "Chronix Dashboard should now be accessible at http://chronix.work.gd (DNS propagation may take time)."
else
    echo "Nginx configuration test failed. Please check nginx_chronix.conf."
    exit 1
fi
