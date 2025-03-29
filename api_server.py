from flask import Flask, render_template, request
from flask import send_from_directory
from flask_socketio import SocketIO
import subprocess
import threading
import time
import os
import sys
import re
import ssl
from OpenSSL import crypto
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Aternos')))
import eventlet
eventlet.monkey_patch()

import subprocess

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
socketio = SocketIO(app, async_mode='eventlet')

script_running = False


# Functie om privé-informatie te maskeren
def sanitize_output(line):
    # Maskeer bestandspaden (vervang door geanonimiseerde versie)
    line = re.sub(r'/Users/[^/]+', '/Users/****', line)
    # Verberg volledige stacktraces, maar behoud de foutmelding
    if "Traceback" in line and "Error:" not in line:
        return "Er is een fout opgetreden in het script."
    # Verberg andere gevoelige informatie
    line = re.sub(r'USERNAME = "[^"]+"', 'USERNAME = "****"', line)
    line = re.sub(r'PASSWORD = "[^"]+"', 'PASSWORD = "****"', line)
    line = re.sub(r'CHROME_PROXY = "[^"]+"', 'CHROME_PROXY = "****"', line)
    return line

def run_script(sid):
    global script_running
    script_running = True
    
    socketio.emit('output', {'data': 'Server wordt gestart...'}, room=sid)
    
    try:
        # Voer het script uit met python3
        env = os.environ.copy()
        env["USERNAME"] = os.getenv("USERNAME", "")
        env["PASSWORD"] = os.getenv("PASSWORD", "")
        env["CHROME_PROXY"] = os.getenv("CHROME_PROXY", "")
        process = subprocess.Popen(
            ["python3", "main.py"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=env
        )
        
        for line in iter(process.stdout.readline, ''):
            # Sanitize de output voor privacy
            safe_line = sanitize_output(line.strip())
            socketio.emit('output', {'data': safe_line}, room=sid)
            time.sleep(0.01)
        
        process.stdout.close()
        process.wait()
        
        if process.returncode == 0:
            socketio.emit('output', {'data': 'Server is succesvol online!'}, room=sid)
        else:
            socketio.emit('output', {'data': 'Er was een probleem bij het starten van de server.'}, room=sid)
    
    except Exception as e:
        socketio.emit('output', {'data': f'Er is een probleem opgetreden: {str(e)}'}, room=sid)
    
    socketio.emit('output', {'data': 'SCRIPT_COMPLETED'}, room=sid)
    script_running = False

@app.route('/')
def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Minecraft Server Controller</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background-color: #f7f7f7; }
            .container { max-width: 800px; margin: 0 auto; background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { color: #333; }
            .button { display: inline-block; background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold; cursor: pointer; border: none; }
            .button:hover { background-color: #45a049; }
            .button:disabled { background-color: #cccccc; cursor: not-allowed; }
            #output { font-family: monospace; height: 400px; overflow-y: auto; background-color: #333; color: #eee; padding: 10px; border-radius: 5px; margin-top: 20px; }
            .success { color: #afa; }
            .error { color: #faa; }
            .timestamp { color: #aaf; }
            .status { margin-top: 15px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Nick90NL's Minecraft Server Controller</h1>
            <p>Klik op de onderstaande knop om de Minecraft server te starten:</p>
            <button id="start-button" class="button">Start de Server</button>
            <p class="status" id="status">Status: Wachten op actie</p>
            <div id="output"></div>
        </div>
        
        <script type="text/javascript">
            document.addEventListener('DOMContentLoaded', () => {
                if (window.socket) {
                    window.socket.disconnect();
                }
                window.socket = io();
                var output = document.getElementById('output');
                var startButton = document.getElementById('start-button');
                var statusText = document.getElementById('status');
                
                startButton.addEventListener('click', () => {
                    output.innerHTML = '';
                    socket.emit('start_script');
                    startButton.disabled = true;
                    startButton.textContent = 'Server wordt gestart...';
                    statusText.textContent = 'Status: Server wordt gestart...';
                    statusText.className = 'status timestamp';
                });
                
                socket.on('output', (msg) => {
                    let line = msg.data;
                    
                    if (line === 'SCRIPT_COMPLETED') {
                        startButton.disabled = false;
                        startButton.textContent = 'Start de Server';
                        statusText.textContent = 'Status: Gereed voor volgende actie';
                        statusText.className = 'status';
                        return;
                    }
                    
                    // Style de output
                    if (line.includes('✓') || line.includes('success') || line.includes('succesvol') || line.includes('online')) {
                        line = `<div class="success">${line}</div>`;
                        if (line.includes('online')) {
                            statusText.textContent = 'Status: Server is online!';
                            statusText.className = 'status success';
                        }
                    } else if (line.includes('✗') || line.includes('error') || line.includes('fout') || line.includes('Error') || line.includes('probleem')) {
                        line = `<div class="error">${line}</div>`;
                        if (line.includes('probleem')) {
                            statusText.textContent = 'Status: Er is een probleem opgetreden';
                            statusText.className = 'status error';
                        }
                    } else if (line.includes('[') && line.includes(']')) { // Timestamp
                        const parts = line.split(']', 1);
                        if (parts.length > 0) {
                            const timestamp = parts[0] + ']';
                            const rest = line.substring(timestamp.length);
                            line = `<div><span class="timestamp">${timestamp}</span>${rest}</div>`;
                        } else {
                            line = `<div>${line}</div>`;
                        }
                    } else {
                        line = `<div>${line}</div>`;
                    }
                    
                    output.innerHTML += line;
                    output.scrollTop = output.scrollHeight;
                });
            });
        </script>
    </body>
    </html>
    """

@app.route('/screens/<path:filename>')
def download_file(filename):
    return send_from_directory('screens', filename)

@socketio.on('start_script')
def handle_start(data=None):
    sid = request.sid
    if not script_running:
        thread = threading.Thread(target=run_script, args=(sid,))
        thread.daemon = True
        thread.start()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=8080)
