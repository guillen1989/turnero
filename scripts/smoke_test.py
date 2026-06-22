#!/usr/bin/env python
"""
Smoke tests post-deploy.

Uso:
    python scripts/smoke_test.py https://tu-app.railway.app
    APP_URL=https://tu-app.railway.app python scripts/smoke_test.py
"""
import os
import sys
import time
import requests

GREEN = "\033[32m"
RED   = "\033[31m"
RESET = "\033[0m"

RETRIES    = 3
RETRY_WAIT = 60  # segundos entre reintentos


def check(session, method, url, expected_status, expected_text=None, label=None):
    label = label or f"{method} {url}"
    try:
        r = session.request(method, url, allow_redirects=False, timeout=10)
    except requests.RequestException as e:
        print(f"{RED}  ✗  {label}  — error de red: {e}{RESET}")
        return False

    status_ok = r.status_code == expected_status
    text_ok   = expected_text is None or expected_text in r.text

    if status_ok and text_ok:
        print(f"{GREEN}  ✓  {label}{RESET}")
        return True
    else:
        detail = f"status {r.status_code} (esperado {expected_status})"
        if not text_ok:
            detail += f", texto «{expected_text}» no encontrado"
            print(f"{RED}  ✗  {label}  — {detail}{RESET}")
            print(f"       Respuesta: {r.text[:300]!r}")
            cache_hdrs = {k: v for k, v in r.headers.items()
                          if k.lower() in ('cache-control', 'age', 'x-cache',
                                           'cf-cache-status', 'x-railway-edge',
                                           'via', 'server')}
            print(f"       Headers caché: {cache_hdrs}")
        else:
            print(f"{RED}  ✗  {label}  — {detail}{RESET}")
        return False


def run_once(base):
    session = requests.Session()
    results = []

    results.append(check(session, "GET", f"{base}/auth/login",         200, "Turnero", "login carga"))
    results.append(check(session, "GET", f"{base}/manifest.json",      200, "Turnero", "PWA manifest"))
    results.append(check(session, "GET", f"{base}/sw.js",              200, None,      "service worker"))
    results.append(check(session, "GET", f"{base}/static/css/main.css",200, None,      "CSS principal"))
    results.append(check(session, "GET", f"{base}/",                   200, None,      "/ carga (no 500)"))
    results.append(check(session, "GET", f"{base}/publicar",           302, None,      "/publicar redirige (no 500)"))
    results.append(check(session, "GET", f"{base}/cambios",            302, None,      "/cambios redirige (no 500)"))

    passed = sum(results)
    total  = len(results)
    print(f"\n{passed}/{total} checks pasados")
    return passed == total


def run(base):
    base = base.rstrip("/")

    for attempt in range(1, RETRIES + 1):
        print(f"\nSmoke tests → {base}  (intento {attempt}/{RETRIES})\n")
        if run_once(base):
            print(f"{GREEN}Deploy OK.{RESET}")
            return
        if attempt < RETRIES:
            print(f"\n  Reintentando en {RETRY_WAIT}s (Railway puede estar en rolling deploy)…\n")
            time.sleep(RETRY_WAIT)

    print(f"{RED}Deploy con problemas tras {RETRIES} intentos.{RESET}")
    sys.exit(1)


if __name__ == "__main__":
    url = (sys.argv[1] if len(sys.argv) > 1 else None) or os.environ.get("APP_URL")
    if not url:
        print("Uso: python scripts/smoke_test.py <url>")
        print("  o: APP_URL=<url> python scripts/smoke_test.py")
        sys.exit(1)
    run(url)
