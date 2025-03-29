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
    libxss1 \
    libgtk-3-0 \
    libgbm1 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    xdg-utils \
    --no-install-recommends \
 && rm -rf /var/lib/apt/lists/*


# Download Chrome 115 via Dropbox direct link
RUN curl -L "https://www.dropbox.com/scl/fi/dm14bbnjtrswffpocrpn0/chrome-linux64.zip?rlkey=xyozt2gjhqkhcep29pmktuuhd&st=8m4jw88j&dl=1" -o chrome.zip \
    && unzip chrome.zip -d /opt/ \
    && ln -s /opt/chrome-linux64/chrome /usr/bin/google-chrome \
    && chmod +x /opt/chrome-linux64/chrome \
    && /usr/bin/google-chrome --version \
    && rm chrome.zip

# Download Chromedriver 115 via Dropbox direct link
RUN curl -L "https://www.dropbox.com/scl/fi/wlubmfu89oec6qj2a59aq/chromedriver-linux64.zip?rlkey=8693aus3c9efd4d443vf4jp85&st=l6q52fsy&dl=1" -o chromedriver.zip \
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