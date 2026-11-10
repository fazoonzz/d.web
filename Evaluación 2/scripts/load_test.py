"""Prueba de carga reproducible (Módulo 9). Solo stdlib + requests.

Mide, contra el stack levantado (docker compose up):
  * catálogo público          GET  /api/v1/products
  * agregación GraphQL        POST /api/v1/graphql  (misPedidos con items y productos; requiere sesión)
Registra: concurrencia, duración, throughput, latencia p50/p95/p99, errores (429 se cuentan aparte) y
CPU/memoria de los contenedores (docker stats, muestreado durante la prueba).

IMPORTANTE: el gateway limita solicitudes por IP (LIMIT_DEFAULT, 120/min por defecto). Para medir capacidad y no
el limitador, levanta el stack con  LIMIT_DEFAULT=100000  LIMIT_AUTH=100000  .

Uso:
  set -a; . ./.env; set +a
  python scripts/load_test.py --concurrency 50 --duration 30 --out docs/evidencias/carga.json
"""
import argparse
import json
import os
import platform
import statistics
import subprocess
import threading
import time
import uuid

import requests

GW = os.getenv("GATEWAY_URL", "http://localhost:8000") + "/api/v1"
GQL = "query{ misPedidos(limit: 10){ id estado total items{ nombre cantidad producto{ nombre precio } } } }"


def pct(values, p):
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, int(round(p / 100 * (len(s) - 1))))] * 1000, 1)


def prepare_user():
    """Crea un cliente de prueba con 3 pedidos para que la agregación tenga datos reales."""
    s = requests.Session()
    email, pw = f"carga{uuid.uuid4().hex[:8]}@prueba.test", "ClaveDePrueba#2026"
    r = s.post(f"{GW}/auth/register", json={"email": email, "password": pw, "nombre": "Carga"})
    assert r.status_code == 201, (r.status_code, r.text)
    assert s.post(f"{GW}/auth/login", json={"email": email, "password": pw}).status_code == 200
    entrega = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() + 3 * 86400))
    for _ in range(3):
        r = s.post(f"{GW}/orders", json={"items": [{"product_id": 1, "cantidad": 1}, {"product_id": 2, "cantidad": 1}],
                                         "direccion_entrega": "Av. Pajaritos 1234, Maipú", "fecha_entrega": entrega})
        assert r.status_code == 201, r.text
    return s.cookies.get("session_token")


def worker(name, stop_at, results, token):
    s = requests.Session()
    if token:
        s.cookies.set("session_token", token)
    lat, codes = [], {}
    while time.time() < stop_at:
        t = time.perf_counter()
        try:
            if name == "catalogo":
                r = s.get(f"{GW}/products", timeout=10)
            else:
                r = s.post(f"{GW}/graphql", json={"query": GQL}, timeout=10)
            code = r.status_code
        except requests.RequestException:
            code = "error_red"
        lat.append(time.perf_counter() - t)
        codes[code] = codes.get(code, 0) + 1
    results.append((lat, codes))


def sample_stats(stop_evt, samples):
    while not stop_evt.is_set():
        try:
            out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{json .}}"],
                                 capture_output=True, text=True, timeout=20).stdout
            for line in out.splitlines():
                d = json.loads(line)
                samples.setdefault(d["Name"], []).append((float(d["CPUPerc"].rstrip("%")), d["MemUsage"].split("/")[0].strip()))
        except Exception:
            return      
        stop_evt.wait(2)


def mem_mib(s):
    n = float("".join(c for c in s if c.isdigit() or c == "."))
    return n * (1024 if s.upper().endswith("GIB") else 1 if s.upper().endswith("MIB") else 1 / 1024)


def run(name, concurrency, duration, token):
    results, stop_evt, samples = [], threading.Event(), {}
    t_stats = threading.Thread(target=sample_stats, args=(stop_evt, samples), daemon=True)
    t_stats.start()
    start = time.time()
    stop_at = start + duration
    threads = [threading.Thread(target=worker, args=(name, stop_at, results, token)) for _ in range(concurrency)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    elapsed = time.time() - start
    stop_evt.set()
    t_stats.join(timeout=25)
    lat = [x for r in results for x in r[0]]
    codes = {}
    for _, c in results:
        for k, v in c.items():
            codes[str(k)] = codes.get(str(k), 0) + v
    total = len(lat)
    ok = codes.get("200", 0)
    limited = codes.get("429", 0)
    res = {
        "escenario": name, "concurrencia": concurrency, "duracion_s": round(elapsed, 1), "solicitudes": total,
        "throughput_rps": round(total / elapsed, 1), "latencia_ms": {
            "p50": pct(lat, 50), "p95": pct(lat, 95), "p99": pct(lat, 99), "max": round(max(lat) * 1000, 1) if lat else None,
            "media": round(statistics.mean(lat) * 1000, 1) if lat else None},
        "codigos": codes, "exitosas_200": ok, "limitadas_429": limited,
        "errores_reales": total - ok - limited, "tasa_error_pct": round(100 * (total - ok - limited) / max(total, 1), 2),
    }
    if samples:
        res["recursos"] = {n: {"cpu_pct_max": max(c for c, _ in v), "cpu_pct_media": round(statistics.mean(c for c, _ in v), 1),
                               "mem_mib_max": round(max(mem_mib(m) for _, m in v), 1)}
                           for n, v in sorted(samples.items())}
    else:
        res["recursos"] = "docker stats no disponible: ejecuta `docker stats --no-stream` aparte"
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--concurrency", type=int, default=50)
    ap.add_argument("--duration", type=int, default=30)
    ap.add_argument("--out", default="carga.json")
    a = ap.parse_args()
    token = prepare_user()
    report = {
        "entorno": {"so": platform.platform(), "python": platform.python_version(), "cpu_logicas": os.cpu_count(),
                    "fecha": time.strftime("%Y-%m-%d %H:%M:%S"), "tipo": "medición local (docker compose en un solo equipo)"},
        "datos": "6 productos sembrados; usuario de carga con 3 pedidos de 2 ítems",
        "resultados": [run("catalogo", a.concurrency, a.duration, None), run("graphql_misPedidos", a.concurrency, a.duration, token)],
    }
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    for r in report["resultados"]:
        print(f"{r['escenario']}: {r['throughput_rps']} req/s · p95 {r['latencia_ms']['p95']} ms · "
              f"200={r['exitosas_200']} 429={r['limitadas_429']} errores={r['errores_reales']}")
    print(f"Reporte: {a.out}")


if __name__ == "__main__":
    main()
