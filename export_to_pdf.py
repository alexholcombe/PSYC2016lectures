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
import hashlib
import base64
import subprocess
import urllib.request
from urllib.parse import urlparse

# How long (seconds) to wait for all images to load after page load event
MAX_IMAGE_WAIT = 15
# How long (seconds) to wait for Page.loadEventFired after navigation
MAX_LOAD_WAIT = 30

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
    """Send a masked WebSocket text frame."""
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

def recv_ws_frame(sock):
    """Read a single WebSocket frame and return the payload bytes."""
    hdr = b''
    while len(hdr) < 2:
        hdr += sock.recv(2 - len(hdr))
    b0, b1 = hdr[0], hdr[1]
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F
    if length == 126:
        ext = b''
        while len(ext) < 2:
            ext += sock.recv(2 - len(ext))
        length = struct.unpack('!H', ext)[0]
    elif length == 127:
        ext = b''
        while len(ext) < 8:
            ext += sock.recv(8 - len(ext))
        length = struct.unpack('!Q', ext)[0]
    if masked:
        mask_key = b''
        while len(mask_key) < 4:
            mask_key += sock.recv(4 - len(mask_key))
    payload = b''
    while len(payload) < length:
        payload += sock.recv(length - len(payload))
    if masked:
        payload = bytearray(payload)
        for i in range(len(payload)):
            payload[i] ^= mask_key[i % 4]
        payload = bytes(payload)
    return payload

def cdp_send(sock, msg_id, method, params=None):
    """Send a CDP command over WebSocket."""
    msg = {'id': msg_id, 'method': method}
    if params:
        msg['params'] = params
    send_ws_frame(sock, json.dumps(msg))

def cdp_recv_until(sock, predicate, timeout=30):
    """Read WS frames until predicate(parsed_json) returns truthy, or timeout."""
    sock.settimeout(timeout)
    deadline = time.time() + timeout
    messages = []
    while time.time() < deadline:
        try:
            frame = recv_ws_frame(sock)
            parsed = json.loads(frame.decode('utf-8', errors='replace'))
            messages.append(parsed)
            result = predicate(parsed)
            if result:
                return result, messages
        except socket.timeout:
            break
    return None, messages

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
    time.sleep(1.5)
    
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
        
        # Enable Page domain events so we get Page.loadEventFired
        cdp_send(sock, 10, 'Page.enable')
        # Drain the response to Page.enable
        cdp_recv_until(sock, lambda m: m.get('id') == 10, timeout=5)
        
        # Wait for Page.loadEventFired (the page may have already loaded, so also check)
        print("    Waiting for page load...", flush=True)
        cdp_recv_until(
            sock,
            lambda m: m.get('method') == 'Page.loadEventFired',
            timeout=MAX_LOAD_WAIT
        )
        
        # Now poll JavaScript to check that all images (including CSS background-image) are loaded
        # This JS snippet checks:
        # 1. All <img> elements have .complete == true and .naturalWidth > 0
        # 2. All elements with a CSS background-image url() have had their images loaded
        check_images_js = r"""
        (function() {
            // Check all <img> elements
            var imgs = document.querySelectorAll('img');
            for (var i = 0; i < imgs.length; i++) {
                if (!imgs[i].complete || imgs[i].naturalWidth === 0) {
                    return JSON.stringify({ready: false, reason: 'img not loaded: ' + imgs[i].src});
                }
            }
            // Check all elements with CSS background-image
            var allEls = document.querySelectorAll('*');
            var bgUrls = [];
            for (var j = 0; j < allEls.length; j++) {
                var bg = getComputedStyle(allEls[j]).backgroundImage;
                if (bg && bg !== 'none' && bg.indexOf('url(') !== -1) {
                    // Extract URLs
                    var matches = bg.match(/url\(["']?([^"')]+)["']?\)/g);
                    if (matches) {
                        for (var k = 0; k < matches.length; k++) {
                            var u = matches[k].replace(/url\(["']?/, '').replace(/["']?\)/, '');
                            if (u && u.indexOf('data:') !== 0) {
                                bgUrls.push(u);
                            }
                        }
                    }
                }
            }
            // Verify background image URLs are fetchable/cached by creating Image objects
            // (they should already be cached by the browser)
            if (bgUrls.length > 0 && !window.__bgImagesChecked) {
                window.__bgImagesChecked = true;
                window.__bgImagesReady = false;
                window.__bgImagesCount = bgUrls.length;
                window.__bgImagesLoaded = 0;
                for (var m = 0; m < bgUrls.length; m++) {
                    var testImg = new Image();
                    testImg.onload = function() {
                        window.__bgImagesLoaded++;
                        if (window.__bgImagesLoaded >= window.__bgImagesCount) {
                            window.__bgImagesReady = true;
                        }
                    };
                    testImg.onerror = function() {
                        window.__bgImagesLoaded++;
                        if (window.__bgImagesLoaded >= window.__bgImagesCount) {
                            window.__bgImagesReady = true;
                        }
                    };
                    testImg.src = bgUrls[m];
                }
                return JSON.stringify({ready: false, reason: 'checking ' + bgUrls.length + ' background images'});
            }
            if (window.__bgImagesChecked && !window.__bgImagesReady) {
                return JSON.stringify({ready: false, reason: 'background images loading: ' + window.__bgImagesLoaded + '/' + window.__bgImagesCount});
            }
            return JSON.stringify({ready: true, imgCount: imgs.length, bgCount: bgUrls.length});
        })()
        """
        
        print("    Waiting for all images to load...", flush=True)
        deadline = time.time() + MAX_IMAGE_WAIT
        images_ready = False
        while time.time() < deadline:
            msg_id = 100 + int(time.time() * 10) % 10000
            cdp_send(sock, msg_id, 'Runtime.evaluate', {
                'expression': check_images_js,
                'returnByValue': True
            })
            result, _ = cdp_recv_until(
                sock,
                lambda m: m.get('id') == msg_id,
                timeout=5
            )
            if result:
                try:
                    val = result.get('result', {}).get('result', {}).get('value', '{}')
                    status = json.loads(val)
                    if status.get('ready'):
                        print(f"    All images ready (img: {status.get('imgCount', '?')}, bg: {status.get('bgCount', '?')})", flush=True)
                        images_ready = True
                        break
                    else:
                        print(f"    ... {status.get('reason', 'waiting')}", flush=True)
                except (json.JSONDecodeError, AttributeError):
                    pass
            time.sleep(0.5)
        
        if not images_ready:
            print("    Warning: timed out waiting for images, proceeding anyway", flush=True)
        
        # Extra settle time for CSS rendering after images are decoded
        time.sleep(1.0)
        
        # Issue printToPDF with background graphics enabled
        cdp_send(sock, 1, 'Page.printToPDF', {
            'printBackground': True,
            'preferCSSPageSize': True,
            'marginTop': 0,
            'marginBottom': 0,
            'marginLeft': 0,
            'marginRight': 0
        })
        
        # Read WebSocket response - the PDF data can be very large
        # so we need to accumulate frames and parse the full JSON
        print("    Generating PDF...", flush=True)
        sock.settimeout(120)
        accumulated = b''
        while True:
            try:
                frame = recv_ws_frame(sock)
                accumulated += frame
                # Try to parse as JSON - if it works and has our id, we're done
                try:
                    resp = json.loads(accumulated.decode('utf-8', errors='replace'))
                    if resp.get('id') == 1 and 'result' in resp:
                        b64_data = resp['result'].get('data', '')
                        if b64_data:
                            pdf_bytes = base64.b64decode(b64_data)
                            with open(out_pdf, 'wb') as f:
                                f.write(pdf_bytes)
                            return True
                        return False
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # Incomplete - keep reading frames
                    continue
            except socket.timeout:
                print("    Warning: timeout reading PDF response", flush=True)
                break
    finally:
        try:
            proc.terminate()
            proc.wait(timeout=3)
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
