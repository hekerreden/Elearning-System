# -*- coding: utf-8 -*-
"""DNS patch for Android — DoH based, safe for multiple imports."""
import socket
import json
import ssl
import urllib.request

# Guard against double-patching
if getattr(socket, "_doh_patch_installed", False):
    pass
else:
    DOH_URLS = [
        "https://cloudflare-dns.com/dns-query",
        "https://dns.google/dns-query",
    ]

    def _doh_query(name, qtype):
        last_err = None
        for base in DOH_URLS:
            try:
                url = f"{base}?name={name}&type={qtype}"
                req = urllib.request.Request(url, headers={
                    "Accept": "application/dns-json",
                    "User-Agent": "Mozilla/5.0",
                })
                ctx = ssl.create_default_context()
                with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                    return json.loads(r.read().decode())
            except Exception as e:
                last_err = e
                continue
        raise RuntimeError(f"DoH failed: {last_err}")

    def resolve_a(name):
        data = _doh_query(name, "A")
        for a in data.get("Answer", []):
            if a.get("type") == 1:
                return a["data"]
        return None

    _orig_gethostbyname = socket.gethostbyname

    def _patched_gethostbyname(host):
        try:
            return _orig_gethostbyname(host)
        except socket.gaierror:
            ip = resolve_a(host)
            if ip:
                return ip
            raise

    socket.gethostbyname = _patched_gethostbyname
    socket._doh_patch_installed = True

    print("✅ DNS patch loaded (DoH mode)")
    try:
        ip = socket.gethostbyname("google.com")
        print(f"   Test google.com → {ip}")
    except Exception as e:
        print(f"   ⚠️ Test failed: {e}")