#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Genera assets/stats.svg: tarjeta animada de estadísticas con estilo de terminal.
Solo usa la biblioteca estándar de Python.

Variables de entorno:
  GITHUB_TOKEN / GH_TOKEN   token para la API (en Actions basta con el token por defecto)
  GH_USER                   usuario a consultar (por defecto, el dueño del repositorio)

Uso: python scripts/generate_stats.py [ruta_de_salida.svg]
"""
import json
import os
import sys
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "Eddglitch"
TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
API = "https://api.github.com"
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Paleta y tipografía (mismas que el banner)
BG, BORDER, TRACK = "#0f1218", "#2b3240", "#1b2029"
TXT, SOFT, DIM = "#d6dde6", "#aab4c3", "#6b7587"
AMBER, BLUE = "#f2b45a", "#7aa2f7"
FONT = "'Cascadia Code','Fira Code',Consolas,'DejaVu Sans Mono',monospace"

# Línea de tiempo de la animación (segundos)
T, RESET = 16.0, 15.2
X0 = 24


# ---------------------------------------------------------------- datos ---
def _pedir(url, cuerpo=None):
    cab = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "perfil-stats",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if TOKEN:
        cab["Authorization"] = "Bearer " + TOKEN
    datos = None
    if cuerpo is not None:
        datos = json.dumps(cuerpo).encode("utf-8")
        cab["Content-Type"] = "application/json"
    peticion = urllib.request.Request(url, data=datos, headers=cab)
    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        return json.load(respuesta)


def obtener():
    """Consulta la API y devuelve los datos que dibuja la tarjeta."""
    if not TOKEN:
        sys.exit("Falta GITHUB_TOKEN (o GH_TOKEN): la API GraphQL lo exige.")

    repos, pagina = [], 1
    while True:
        lote = _pedir(f"{API}/users/{USER}/repos?type=owner&per_page=100&page={pagina}")
        repos += lote
        if len(lote) < 100:
            break
        pagina += 1

    propios = [r for r in repos if not r["fork"]]
    por_lenguaje = {}
    for r in propios:
        for lenguaje, n in _pedir(f"{API}/repos/{USER}/{r['name']}/languages").items():
            por_lenguaje[lenguaje] = por_lenguaje.get(lenguaje, 0) + n

    consulta = (
        "query($login:String!){user(login:$login){contributionsCollection{"
        "contributionCalendar{weeks{contributionDays{contributionCount date}}}}}}"
    )
    g = _pedir(f"{API}/graphql", {"query": consulta, "variables": {"login": USER}})
    if "errors" in g:
        sys.exit("Error de GraphQL: " + json.dumps(g["errors"]))
    semanas = g["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"][-52:]

    dias = [d for s in semanas for d in s["contributionDays"]]
    total_bytes = sum(por_lenguaje.values()) or 1
    top = sorted(por_lenguaje.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "repos": len(propios),
        "contribs": sum(d["contributionCount"] for d in dias),
        "dias_activos": sum(1 for d in dias if d["contributionCount"] > 0),
        "n_langs": len(por_lenguaje),
        "langs": [(n, 100.0 * b / total_bytes) for n, b in top],
        "semanas": [sum(d["contributionCount"] for d in s["contributionDays"]) for s in semanas],
        "desde": dias[0]["date"],
        "hasta": dias[-1]["date"],
    }


# ------------------------------------------------------------ animación ---
def _fmt(v):
    return f"{v:g}" if isinstance(v, (int, float)) else str(v)


def anim(attr, segs):
    """Animación discreta: cada (t, valor) se mantiene hasta el siguiente."""
    kt = ";".join(f"{t / T:.4f}" for t, _ in segs)
    vals = ";".join(_fmt(v) for _, v in segs)
    return (f'<animate attributeName="{attr}" calcMode="discrete" dur="{T}s" '
            f'repeatCount="indefinite" keyTimes="{kt}" values="{vals}"/>')


def lin(attr, segs):
    """Animación lineal (interpola entre puntos)."""
    kt = ";".join(f"{t / T:.4f}" for t, _ in segs)
    vals = ";".join(_fmt(v) for _, v in segs)
    return (f'<animate attributeName="{attr}" dur="{T}s" repeatCount="indefinite" '
            f'keyTimes="{kt}" values="{vals}"/>')


def aparece(t_on):
    return anim("opacity", [(0, 0), (t_on, 1), (RESET, 0)])


def crece(attr, t0, dur, ancho_final, base=0):
    """Crece de `base` a `ancho_final` y vuelve a base al reiniciar el ciclo."""
    return lin(attr, [(0, base), (t0, base), (t0 + dur, ancho_final),
                      (RESET, ancho_final), (RESET + 0.05, base), (T, base)])


def mascara(x, y, w, h, t0, dur, n):
    """Rectángulo del color de fondo que descubre el texto carácter por carácter."""
    dt, cw = dur / n, w / n
    xs = [(0, x)] + [(t0 + i * dt, x + (i + 1) * cw) for i in range(n)] + [(RESET, x)]
    ws = [(0, w + 6)] + [(t0 + i * dt, w + 6 - (i + 1) * cw) for i in range(n)] + [(RESET, w + 6)]
    return (f'<rect x="{x + w:g}" y="{y}" width="0" height="{h}" fill="{BG}">'
            f'{anim("x", xs)}{anim("width", ws)}</rect>')


def texto(x, y, s, size=15, fill=TXT, peso=None):
    w = len(s) * size * 0.6
    p = f' font-weight="{peso}"' if peso else ""
    return (f'<text x="{x:g}" y="{y}" font-size="{size}" fill="{fill}"{p} textLength="{w:g}" '
            f'lengthAdjust="spacing" font-family="{FONT}">{escape(s)}</text>')


def grupo(t_on, *hijos):
    return f'<g>{aparece(t_on)}' + "".join(hijos) + "</g>"


def prompt(y, t_on=None):
    pw = 14 * 9.6
    a = aparece(t_on) if t_on is not None else ""
    return (f'<text x="{X0}" y="{y}" font-size="16" textLength="{pw:g}" lengthAdjust="spacing" '
            f'font-family="{FONT}"><tspan fill="{AMBER}">edd@glitch</tspan>'
            f'<tspan fill="{DIM}">:</tspan><tspan fill="{BLUE}">~</tspan>'
            f'<tspan fill="{TXT}">$ </tspan>{a}</text>'), X0 + pw


def etiqueta_fecha(iso):
    return f"{MESES[int(iso[5:7]) - 1]} {iso[:4]}"


# ---------------------------------------------------------------- dibujo ---
def render(d):
    H = 396
    p = []
    p.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 880 {H}" width="880" height="{H}" '
             f'role="img" aria-labelledby="t d">')
    p.append(f'<title id="t">edd@glitch:~$ ./stats.sh --user {escape(USER)}</title>')
    resumen = (f'{d["repos"]} repositorios públicos propios, {d["contribs"]} contribuciones en 52 semanas, '
               f'{d["dias_activos"]} días activos y {d["n_langs"]} lenguajes.')
    p.append(f'<desc id="d">Tarjeta de estadísticas estilo terminal. {escape(resumen)}</desc>')
    p.append(f'<rect x="1" y="1" width="878" height="{H - 2}" rx="10" fill="{BG}" stroke="{BORDER}"/>')
    p.append(f'<path d="M1 34 H879" stroke="{BORDER}"/>')
    for cx in (22, 42, 62):
        p.append(f'<circle cx="{cx}" cy="17" r="5" fill="#3a4150"/>')
    p.append(f'<text x="440" y="21" font-size="12" fill="{DIM}" text-anchor="middle" '
             f'font-family="{FONT}">edd@glitch: ~/stats</text>')

    # Comando tecleado
    pr, cx = prompt(76)
    p.append(pr)
    cmd = f"./stats.sh --user {USER}"
    w = len(cmd) * 9.6
    p.append(f'<text x="{cx:g}" y="76" font-size="16" fill="{TXT}" textLength="{w:g}" '
             f'lengthAdjust="spacing" font-family="{FONT}">{escape(cmd)}</text>')
    p.append(mascara(cx, 62, w, 20, 0.4, 1.4, len(cmd)))

    # Resumen (columna izquierda)
    p.append(grupo(2.0, texto(X0, 114, "# resumen", 13, DIM)))
    filas = [("repos públicos", d["repos"]), ("contribuciones", d["contribs"]),
             ("días activos", d["dias_activos"]), ("lenguajes", d["n_langs"])]
    for i, (clave, valor) in enumerate(filas):
        y = 142 + i * 24
        p.append(grupo(2.2 + i * 0.18, texto(X0, y, clave, 15, SOFT),
                       texto(230, y, str(valor), 15, AMBER, 600)))

    # Lenguajes (columna derecha)
    p.append(grupo(2.0, texto(440, 114, "# lenguajes (bytes, repos propios)", 13, DIM)))
    for i, (nombre, pct) in enumerate(d["langs"]):
        y = 142 + i * 24
        ancho = max(2.0, 170 * pct / 100.0)
        barra = (f'<rect x="600" y="{y - 11}" width="{ancho:g}" height="10" rx="2" fill="{BLUE}" '
                 f'fill-opacity="{1 - i * 0.14:.2f}">{crece("width", 2.4 + i * 0.18, 0.8, ancho)}</rect>')
        p.append(grupo(2.2 + i * 0.18,
                       texto(440, y, nombre[:16], 15, SOFT),
                       f'<rect x="600" y="{y - 11}" width="170" height="10" rx="2" fill="{TRACK}"/>',
                       barra,
                       texto(782, y, f"{pct:.1f}%", 15, TXT)))

    # Actividad semanal (ancho completo)
    sem = d["semanas"]
    n = len(sem)
    p.append(grupo(4.3, texto(X0, 270, f"# actividad semanal ({n} semanas)", 13, DIM)))
    base, alto_max = 330, 44
    paso = 832.0 / n
    pico = max(sem) or 1
    for i, c in enumerate(sem):
        h = max(2, round(alto_max * c / pico)) if c > 0 else 2
        x = X0 + i * paso
        color, op = (AMBER, 0.45 + 0.55 * c / pico) if c > 0 else (BORDER, 1)
        t0 = 4.5 + i * 0.02
        p.append(f'<rect x="{x:.1f}" y="{base - h}" width="{paso - 5:.1f}" height="{h}" rx="1.5" '
                 f'fill="{color}" fill-opacity="{op:.2f}">'
                 f'{crece("height", t0, 0.5, h)}{crece("y", t0, 0.5, base - h, base)}</rect>')
    izq, der = etiqueta_fecha(d["desde"]), etiqueta_fecha(d["hasta"])
    centro = f"pico: {pico} contribuciones en una semana"
    p.append(grupo(5.6,
                   texto(X0, 348, izq, 11, DIM),
                   texto(856 - len(der) * 6.6, 348, der, 11, DIM),
                   texto((880 - len(centro) * 6.6) / 2, 348, centro, 11, DIM)))

    # Prompt final con cursor
    pr, cx = prompt(380, t_on=6.4)
    p.append(pr)
    p.append(f'<g>{aparece(6.4)}<rect x="{cx:g}" y="366" width="9" height="17" fill="{AMBER}">'
             f'<animate attributeName="opacity" values="1;0;1" keyTimes="0;0.5;1" calcMode="discrete" '
             f'dur="1s" repeatCount="indefinite"/></rect></g>')
    p.append("</svg>")
    return "\n".join(p) + "\n"


def main():
    salida = sys.argv[1] if len(sys.argv) > 1 else "assets/stats.svg"
    svg = render(obtener())
    os.makedirs(os.path.dirname(os.path.abspath(salida)), exist_ok=True)
    with open(salida, "w", encoding="utf-8", newline="\n") as f:
        f.write(svg)
    print(f"Tarjeta escrita en {salida} ({len(svg)} bytes)")


if __name__ == "__main__":
    main()
