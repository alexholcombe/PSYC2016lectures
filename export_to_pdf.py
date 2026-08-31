#!/usr/bin/env python3
"""
Script: export_to_pdf.py
Exports Quarto / Reveal.js HTML slide decks to PDF using Chrome DevTools Protocol (CDP)
with printBackground=True and preferCSSPageSize=True to preserve all background images,
background colors, transparencies, slide dimensions, and layouts.
"""

import sys
import os
import time
import json
import socket
import struct
import base64
import subprocess
import urllib.request
from urllib.parse import urlparse

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "google-chrome",
    "chromium",
    "chrome",
]

def find_chrome():
    for candidate in CHROME_CANDIDATES:
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            return candidate
        # check PATH
        res = subprocess.run(["which", candidate], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout.strip()
    return None

def send_ws_frame(sock, data_str):
    payload = data_str.encode('utf-8')
    length = len(payload)
    mask = os.urandom(4)
    if length <= 125:
        hdr = struct.pack('!BB', 0x81, 0x80 | length)
    elif length <= 65535:
        hdr = struct.pack('!BBH', 0x81, 0x80 | 126, length)
    else:
        hdr = struct.pack('!BBQ', 0x81, 0x80 | 127, length)
    masked = bytearray(length)
    for i in range(length):
        masked[i] = payload[i] ^ mask[i % 4]
    sock.sendall(hdr + mask + masked)

def export_single_html_to_pdf(chrome_bin, html_file, out_pdf, port=9445):
    # Start Chrome with remote debugging
    cmd = [
        chrome_bin,
        '--headless=new',
        f'--remote-debugging-port={port}',
        '--disable-gpu',
        '--no-first-run',
        '--no-default-browser-check'
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.2)
    
    try:
        url = f'file://{os.path.abspath(html_file)}?view=print'
        req = urllib.request.Request(f'http://127.0.0.1:{port}/json/new?{url}', method='PUT')
        tab = json.loads(urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
        ws_url = tab['webSocketDebuggerUrl']
        
        parsed = urlparse(ws_url)
        sock = socket.create_connection((parsed.hostname, parsed.port), timeout=30)
        
        # WebSocket handshake
        key = base64.b64encode(os.urandom(16)).decode('utf-8')
        handshake = (
            f'GET {parsed.path} HTTP/1.1\r\n'
            f'Host: {parsed.hostname}:{parsed.port}\r\n'
            'Upgrade: websocket\r\n'
            'Connection: Upgrade\r\n'
            f'Sec-WebSocket-Key: {key}\r\n'
            'Sec-WebSocket-Version: 13\r\n\r\n'
        )
        sock.sendall(handshake.encode('utf-8'))
        
        # Wait for handshake completion
        buf = b''
        while b'\r\n\r\n' not in buf:
            chunk = sock.recv(1024)
            if not chunk:
                break
            buf += chunk
        
        # Allow time for reveal.js layout and image decoding
        time.sleep(2.5)
        
        # Issue printToPDF with background graphics enabled
        msg = json.dumps({
            'id': 1,
            'method': 'Page.printToPDF',
            'params': {
                'printBackground': True,
                'preferCSSPageSize': True,
                'marginTop': 0,
                'marginBottom': 0,
                'marginLeft': 0,
                'marginRight': 0
            }
        })
        send_ws_frame(sock, msg)
        
        # Read WebSocket response until id:1 data is found
        raw = b''
        sock.settimeout(60)
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            raw += chunk
            if b'"id":1' in raw and b'"data":"' in raw:
                idx_data = raw.find(b'"data":"')
                if idx_data != -1:
                    end_quote = raw.find(b'"', idx_data + 8)
                    if end_quote != -1:
                        b64_data = raw[idx_data + 8:end_quote].decode('utf-8')
                        pdf_bytes = base64.b64decode(b64_data)
                        with open(out_pdf, 'wb') as f:
                            f.write(pdf_bytes)
                        return True
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            pass
    return False

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(script_dir, "docs")
    pdf_dir = os.path.join(docs_dir, "pdf")
    os.makedirs(pdf_dir, exist_ok=True)
    
    chrome_bin = find_chrome()
    if not chrome_bin:
        print("Error: Google Chrome / Chromium could not be found.", file=sys.stderr)
        sys.exit(1)
        
    print("=" * 60)
    print("Exporting Quarto / Reveal.js HTML presentations to PDF")
    print(f"Chrome binary: {chrome_bin}")
    print(f"Output folder: {pdf_dir}")
    print("Background images/graphics: ENABLED (printBackground=True)")
    print("=" * 60)
    
    html_files = [
        f for f in sorted(os.listdir(docs_dir))
        if f.endswith('.html') and not f.endswith('-speaker.html') and f != 'index.html'
    ]
    
    success = 0
    count = 0
    
    for filename in html_files:
        html_path = os.path.join(docs_dir, filename)
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        if "reveal" not in content or "Redirect to" in content:
            continue
            
        count += 1
        basename_no_ext = os.path.splitext(filename)[0]
        out_pdf = os.path.join(pdf_dir, f"{basename_no_ext}.pdf")
        
        print(f"\n[{count}] Converting: {filename} -> pdf/{basename_no_ext}.pdf")
        ok = export_single_html_to_pdf(chrome_bin, html_path, out_pdf, port=9445 + (count % 10))
        if ok and os.path.exists(out_pdf):
            size_mb = os.path.getsize(out_pdf) / (1024 * 1024)
            print(f"    ✓ Successfully generated ({size_mb:.2f} MB with background images)")
            success += 1
        else:
            print(f"    ✗ Failed to generate {out_pdf}", file=sys.stderr)
            
    print("\n" + "=" * 60)
    print(f"Completed: {success} / {count} slide decks converted to PDF.")
    print(f"PDF files are saved in: {pdf_dir}")
    print("=" * 60)

if __name__ == "__main__":
    main()
