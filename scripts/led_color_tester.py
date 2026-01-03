#!/usr/bin/env python3
"""
LED Color Tester for OpenEVSE
==============================
A simple web-based tool to test LED colors on OpenEVSE wallbox using the
temporary LED color override feature.

Usage:
    python3 led_color_tester.py [--port PORT]

Then open your browser at: http://localhost:8000
"""

import http.server
import socketserver
import argparse
import json
import urllib.request
import urllib.error
from urllib.parse import urlparse, parse_qs

PORT = 8000

# Using raw string to avoid escaping issues
HTML_CONTENT = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OpenEVSE LED Color Tester</title>
    <script src="https://cdn.jsdelivr.net/npm/@jaames/iro@5"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 40px;
            max-width: 500px;
            width: 100%;
        }
        
        h1 {
            color: #333;
            margin-bottom: 10px;
            font-size: 28px;
            text-align: center;
        }
        
        .subtitle {
            color: #666;
            text-align: center;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .form-group {
            margin-bottom: 25px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
            font-size: 14px;
        }
        
        input[type="text"],
        input[type="number"],
        select {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 16px;
            transition: border-color 0.3s;
        }
        
        input[type="text"]:focus,
        input[type="number"]:focus,
        select:focus {
            outline: none;
            border-color: #667eea;
        }
        
        .color-picker-wrapper {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 20px;
        }
        
        #colorPicker {
            margin: 0 auto;
        }
        
        .color-info {
            text-align: center;
            width: 100%;
        }
        
        .color-hex {
            font-size: 28px;
            font-weight: bold;
            color: #333;
            font-family: 'Courier New', monospace;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 12px;
            border: 2px solid #e0e0e0;
        }
        
        .color-values {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 10px;
            margin-top: 15px;
        }
        
        .color-value {
            background: #f8f9fa;
            padding: 10px;
            border-radius: 8px;
            text-align: center;
        }
        
        .color-value-label {
            font-size: 11px;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 5px;
        }
        
        .color-value-number {
            font-size: 16px;
            font-weight: bold;
            color: #333;
            font-family: 'Courier New', monospace;
        }
        
        .slider-container {
            display: flex;
            align-items: center;
            gap: 15px;
        }
        
        input[type="range"] {
            flex: 1;
            height: 8px;
            border-radius: 5px;
            background: #e0e0e0;
            outline: none;
            -webkit-appearance: none;
        }
        
        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #667eea;
            cursor: pointer;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        input[type="range"]::-moz-range-thumb {
            width: 24px;
            height: 24px;
            border-radius: 50%;
            background: #667eea;
            cursor: pointer;
            border: none;
            box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        }
        
        .brightness-value {
            min-width: 50px;
            text-align: center;
            font-weight: bold;
            color: #667eea;
            font-size: 18px;
        }
        
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 30px;
        }
        
        button {
            flex: 1;
            padding: 15px;
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
        }
        
        .btn-primary {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .btn-primary:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
        }
        
        .btn-secondary {
            background: #f0f0f0;
            color: #333;
        }
        
        .btn-secondary:hover {
            background: #e0e0e0;
        }
        
        .status {
            margin-top: 20px;
            padding: 15px;
            border-radius: 8px;
            text-align: center;
            font-size: 14px;
            display: none;
        }
        
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .status.info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        
        .live-update {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 20px;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 8px;
        }
        
        .live-update input[type="checkbox"] {
            width: 20px;
            height: 20px;
            cursor: pointer;
        }
        
        .live-update label {
            margin: 0;
            font-weight: normal;
            cursor: pointer;
        }
        
        .preset-colors {
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: 10px;
            margin-top: 10px;
        }
        
        .preset-color {
            width: 100%;
            aspect-ratio: 1;
            border-radius: 8px;
            cursor: pointer;
            border: 2px solid #e0e0e0;
            transition: transform 0.2s;
        }
        
        .preset-color:hover {
            transform: scale(1.1);
            border-color: #667eea;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🎨 LED Color Tester</h1>
        <p class="subtitle">OpenEVSE Wallbox LED Control</p>
        
        <div class="form-group">
            <label for="hostname">Wallbox Hostname/IP</label>
            <input type="text" id="hostname" value="openevse.local" placeholder="openevse.local or 192.168.1.100">
        </div>
        
        <div class="form-group">
            <label for="state">LED State</label>
            <select id="state">
                <option value="all">All States</option>
                <option value="off">Off State</option>
                <option value="error">Error/Fault State</option>
                <option value="ready">Ready State (not connected)</option>
                <option value="waiting">Waiting State (connected, ready to charge)</option>
                <option value="charging">Charging State</option>
                <option value="custom">Custom State</option>
                <option value="default">Default/Fallback State</option>
            </select>
        </div>
        
        <div class="form-group">
            <label>Color</label>
            <div class="color-picker-wrapper">
                <div id="colorPicker"></div>
                <div class="color-info">
                    <div class="color-hex" id="colorHex">#FFD700</div>
                    <div class="color-values">
                        <div class="color-value">
                            <div class="color-value-label">Red</div>
                            <div class="color-value-number" id="redValue">255</div>
                        </div>
                        <div class="color-value">
                            <div class="color-value-label">Green</div>
                            <div class="color-value-number" id="greenValue">215</div>
                        </div>
                        <div class="color-value">
                            <div class="color-value-label">Blue</div>
                            <div class="color-value-number" id="blueValue">0</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="form-group">
            <label>Preset Colors</label>
            <div class="preset-colors">
                <div class="preset-color" style="background: #FF0000" data-color="#FF0000" title="Red"></div>
                <div class="preset-color" style="background: #00FF00" data-color="#00FF00" title="Green"></div>
                <div class="preset-color" style="background: #0000FF" data-color="#0000FF" title="Blue"></div>
                <div class="preset-color" style="background: #FFFF00" data-color="#FFFF00" title="Yellow"></div>
                <div class="preset-color" style="background: #FF00FF" data-color="#FF00FF" title="Magenta"></div>
                <div class="preset-color" style="background: #00FFFF" data-color="#00FFFF" title="Cyan"></div>
                <div class="preset-color" style="background: #FFA500" data-color="#FFA500" title="Orange"></div>
                <div class="preset-color" style="background: #800080" data-color="#800080" title="Purple"></div>
                <div class="preset-color" style="background: #FFC0CB" data-color="#FFC0CB" title="Pink"></div>
                <div class="preset-color" style="background: #FFFFFF; border-color: #999" data-color="#FFFFFF" title="White"></div>
                <div class="preset-color" style="background: #FFD700" data-color="#FFD700" title="Gold"></div>
                <div class="preset-color" style="background: #4169E1" data-color="#4169E1" title="Royal Blue"></div>
            </div>
        </div>
        
        <div class="form-group">
            <label for="brightness">Brightness</label>
            <div class="slider-container">
                <input type="range" id="brightness" min="0" max="255" value="255">
                <span class="brightness-value" id="brightnessValue">255</span>
            </div>
        </div>
        
        <div class="form-group">
            <label for="timeout">Timeout (seconds, 0 = permanent)</label>
            <input type="number" id="timeout" min="0" max="3600" value="0">
        </div>
        
        <div class="live-update">
            <input type="checkbox" id="liveUpdate" checked>
            <label for="liveUpdate">Live update (changes apply immediately)</label>
        </div>
        
        <div class="button-group">
            <button class="btn-primary" onclick="applyColor()">Apply Color</button>
            <button class="btn-secondary" onclick="resetLED()">Reset</button>
        </div>
        
        <div class="status" id="status"></div>
    </div>
    
    <script>
        const colorHex = document.getElementById('colorHex');
        const redValue = document.getElementById('redValue');
        const greenValue = document.getElementById('greenValue');
        const blueValue = document.getElementById('blueValue');
        const brightnessSlider = document.getElementById('brightness');
        const brightnessValue = document.getElementById('brightnessValue');
        const liveUpdateCheckbox = document.getElementById('liveUpdate');
        const statusDiv = document.getElementById('status');
        
        // Initialize iro.js color picker
        const colorPicker = new iro.ColorPicker('#colorPicker', {
            width: 280,
            color: '#FFD700',
            borderWidth: 2,
            borderColor: '#e0e0e0',
            layout: [
                {
                    component: iro.ui.Wheel,
                    options: {}
                },
                {
                    component: iro.ui.Slider,
                    options: {
                        sliderType: 'value'
                    }
                }
            ]
        });
        
        // Update display when color changes
        colorPicker.on('color:change', (color) => {
            colorHex.textContent = color.hexString.toUpperCase();
            redValue.textContent = color.rgb.r;
            greenValue.textContent = color.rgb.g;
            blueValue.textContent = color.rgb.b;
            
            if (liveUpdateCheckbox.checked) {
                applyColor();
            }
        });
        
        // Update brightness display
        brightnessSlider.addEventListener('input', (e) => {
            brightnessValue.textContent = e.target.value;
            if (liveUpdateCheckbox.checked) {
                applyColor();
            }
        });
        
        // State and timeout changes
        document.getElementById('state').addEventListener('change', () => {
            if (liveUpdateCheckbox.checked) {
                applyColor();
            }
        });
        
        document.getElementById('timeout').addEventListener('change', () => {
            if (liveUpdateCheckbox.checked) {
                applyColor();
            }
        });
        
        // Preset colors
        document.querySelectorAll('.preset-color').forEach(preset => {
            preset.addEventListener('click', (e) => {
                const color = e.target.dataset.color;
                colorPicker.color.hexString = color;
            });
        });
        
        function showStatus(message, type) {
            statusDiv.textContent = message;
            statusDiv.className = `status ${type}`;
            statusDiv.style.display = 'block';
            
            if (type === 'success' || type === 'info') {
                setTimeout(() => {
                    statusDiv.style.display = 'none';
                }, 3000);
            }
        }
        
        async function applyColor() {
            const hostname = document.getElementById('hostname').value;
            const state = document.getElementById('state').value;
            const color = colorPicker.color.hexString;
            const brightness = parseInt(brightnessSlider.value);
            const timeout = parseInt(document.getElementById('timeout').value);
            
            if (!hostname) {
                showStatus('Please enter a hostname or IP address', 'error');
                return;
            }
            
            const payload = {
                hostname: hostname,
                state: state,
                color: color,
                brightness: brightness,
                timeout: timeout
            };
            
            try {
                const response = await fetch('/api/led', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(payload)
                });
                
                const result = await response.json();
                showStatus(`✓ Color applied: ${color} @ ${brightness}`, 'success');
                
            } catch (error) {
                showStatus(`Error: ${error.message}`, 'error');
            }
        }
        
        async function resetLED() {
            const hostname = document.getElementById('hostname').value;
            
            if (!hostname) {
                showStatus('Please enter a hostname or IP address', 'error');
                return;
            }
            
            try {
                const response = await fetch(`/api/led?hostname=${encodeURIComponent(hostname)}`, {
                    method: 'DELETE'
                });
                
                const result = await response.json();
                showStatus('✓ LED override cleared - restored to default behavior', 'success');
                
            } catch (error) {
                showStatus(`Error: ${error.message}`, 'error');
            }
        }
        
        // Initial display update
        const initialColor = colorPicker.color;
        colorHex.textContent = initialColor.hexString.toUpperCase();
        redValue.textContent = initialColor.rgb.r;
        greenValue.textContent = initialColor.rgb.g;
        blueValue.textContent = initialColor.rgb.b;
        brightnessValue.textContent = brightnessSlider.value;
        
        // Show helpful CORS message on load
        setTimeout(() => {
            showStatus('💡 Tip: If colors do not update, check hostname and network connection', 'info');
        }, 1000);
    </script>
</body>
</html>
"""


class LEDColorTesterHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler for LED color tester"""
    
    def do_GET(self):
        """Serve the HTML interface"""
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(HTML_CONTENT.encode('utf-8'))
        else:
            self.send_error(404, "File not found")
    
    def do_POST(self):
        """Proxy POST requests to wallbox"""
        if self.path == '/api/led':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                data = json.loads(post_data.decode('utf-8'))
                hostname = data.get('hostname')
                
                if not hostname:
                    self.send_error(400, "Missing hostname")
                    return
                
                # Remove hostname from payload
                del data['hostname']
                
                # Forward request to wallbox
                url = f"http://{hostname}/led"
                if hostname.startswith('http://') or hostname.startswith('https://'):
                    url = f"{hostname}/led"
                
                req = urllib.request.Request(
                    url,
                    data=json.dumps(data).encode('utf-8'),
                    headers={'Content-Type': 'application/json'},
                    method='POST'
                )
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    response_data = response.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(response_data)
                    
            except urllib.error.URLError as e:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"msg": "Request sent (response unavailable)"}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404, "Not found")
    
    def do_DELETE(self):
        """Proxy DELETE requests to wallbox"""
        if self.path.startswith('/api/led?'):
            # Extract hostname from query string
            query = urlparse(self.path).query
            params = parse_qs(query)
            hostname = params.get('hostname', [None])[0]
            
            if not hostname:
                self.send_error(400, "Missing hostname parameter")
                return
            
            try:
                # Forward DELETE request to wallbox
                url = f"http://{hostname}/led"
                if hostname.startswith('http://') or hostname.startswith('https://'):
                    url = f"{hostname}/led"
                
                req = urllib.request.Request(url, method='DELETE')
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    response_data = response.read()
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(response_data)
                    
            except urllib.error.URLError as e:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps({"msg": "Request sent (response unavailable)"}).encode('utf-8'))
            except Exception as e:
                self.send_error(500, str(e))
        else:
            self.send_error(404, "Not found")
    
    def log_message(self, format, *args):
        """Custom log message format"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    parser = argparse.ArgumentParser(
        description='OpenEVSE LED Color Tester - Web Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 led_color_tester.py
  python3 led_color_tester.py --port 8080

Then open your browser at: http://localhost:8000
"""
    )
    parser.add_argument(
        '--port', 
        type=int, 
        default=8000,
        help='Port to run the web server on (default: 8000)'
    )
    
    args = parser.parse_args()
    
    try:
        with socketserver.TCPServer(("", args.port), LEDColorTesterHandler) as httpd:
            print("=" * 60)
            print("OpenEVSE LED Color Tester")
            print("=" * 60)
            print(f"\n✓ Server started on port {args.port}")
            print(f"\n🌐 Open your browser at:")
            print(f"   http://localhost:{args.port}")
            print(f"   http://127.0.0.1:{args.port}")
            print(f"\n💡 Make sure your wallbox is accessible on your network")
            print(f"\nPress Ctrl+C to stop the server\n")
            
            httpd.serve_forever()
            
    except KeyboardInterrupt:
        print("\n\n✓ Server stopped")
    except OSError as e:
        if e.errno == 98:
            print(f"\n✗ Error: Port {args.port} is already in use")
            print(f"  Try a different port with: --port 8080")
        else:
            print(f"\n✗ Error: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
