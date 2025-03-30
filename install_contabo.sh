#!/bin/bash
set -e

echo "🔧 Systeem updaten en benodigde tools installeren..."
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv unzip curl wget git ca-certificates gnupg libglib2.0-0 libnss3 libgconf-2-4 libx11-xcb1 libxcomposite1 libxcursor1 libxdamage1 libxrandr2 libgbm1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxss1 libgtk-3-0 xdg-utils

echo "🧱 Chrome installeren..."
curl -L "https://www.dropbox.com/scl/fi/dm14bbnjtrswffpocrpn0/chrome-linux64.zip?rlkey=xyozt2gjhqkhcep29pmktuuhd&st=8m4jw88j&dl=1" -o chrome.zip
unzip chrome.zip -d /opt/
ln -sf /opt/chrome-linux64/chrome /usr/bin/google-chrome
chmod +x /opt/chrome-linux64/chrome
rm chrome.zip

echo "🧱 Chromedriver installeren..."
curl -L "https://www.dropbox.com/scl/fi/wlubmfu89oec6qj2a59aq/chromedriver-linux64.zip?rlkey=8693aus3c9efd4d443vf4jp85&st=l6q52fsy&dl=1" -o chromedriver.zip
unzip chromedriver.zip -d /opt/
mv /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver
chmod +x /usr/local/bin/chromedriver
rm chromedriver.zip

echo "🐍 Virtuele Python-omgeving opzetten..."
python3 -m venv venv
source venv/bin/activate

echo "📦 Dependencies installeren..."
pip install --upgrade pip
pip install -r requirements.txt

echo "✅ Installatie voltooid!"
echo "👉 Start de app met: source venv/bin/activate && python3 api_server.py"