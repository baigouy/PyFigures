#!/bin/bash

# Update package lists
sudo apt update

# Install Microsoft Core Fonts (includes Arial)
echo "Installing Microsoft Core Fonts (Arial)..."
sudo apt install -y ttf-mscorefonts-installer

# Install TeX Gyre Heros (Helvetica-like)
echo "Installing TeX Gyre Heros (Helvetica-like)..."
sudo apt install -y fonts-texgyre

# Install Nimbus Sans (another Helvetica-like)
echo "Installing Nimbus Sans (Helvetica-like)..."
sudo apt install -y fonts-nimbus

# Install Liberation fonts (Arial-like)
echo "Installing Liberation fonts (Arial-like)..."
sudo apt install -y fonts-liberation

# Update font cache
echo "Updating font cache..."
sudo fc-cache -f -v

echo "Installation complete!"
