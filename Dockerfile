# Dockerfile voor Render (Flask + Selenium + Chrome)
FROM --platform=linux/amd64 python:3.12-slim

# 2. Zorg dat alles up-to-date is en benodigde tools beschikbaar zijn
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    unzip \
    gnupg \
    ca-certificates \
    fonts-liberation \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libcups2 \
    libdbus-1-3 \
    libgdk-pixbuf2.0-0 \
    libnspr4 \
    libnss3 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*

# Download en installeer Chrome 115 en Chromedriver via OneDrive links
RUN curl -L -o chrome.zip "https://1drv.ms/u/s!AnBCUG_fnhKVl6QCP8N1YYOtFE1Mvw?e=unk0WJ" \
    && unzip chrome.zip -d /opt/ \
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome \
    && rm chrome.zip

RUN curl -L -o chromedriver.zip "https://1drv.ms/u/s!AnBCUG_fnhKVl6QBSDSb3HQiSxi6pg?e=ZxjIBW" \
    && unzip chromedriver.zip -d /opt/ \
    && mv /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && chmod +x /usr/local/bin/chromedriver \
    && rm chromedriver.zip

# 5. Zet werkdirectory en kopieer alle bestanden
WORKDIR /app
COPY . /app
COPY cookies.pkl /app/cookies.pkl

# 6. Installeer Python dependencies
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 7. Expose poort 8080 voor Render
EXPOSE 8080

# 8. Start de Flask app via gunicorn
CMD ["gunicorn", "-k", "eventlet", "-b", "0.0.0.0:8080", "api_server:app"]