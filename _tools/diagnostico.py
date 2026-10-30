#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Diagnóstico de fichas Folklorius — Momento 1 del protocolo folklorius-revision v3.0
Uso: python3 /home/claude/diagnostico.py <slug.html> [slug2.html ...]
No modifica nada. Solo mide.
"""
import sys, os, re, json, datetime, unicodedata

REPO = "/home/claude/folklorius"

# ---------------------------------------------------------------- utilidades

def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    raw = raw.replace(b"\r\n", b"\n")
    return raw.decode("utf-8")

def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")

def visible_text(c):
    t = re.sub(r"(?is)<script.*?</script>", " ", c)
    t = re.sub(r"(?is)<style.*?</style>", " ", t)
    t = re.sub(r"(?s)<!--.*?-->", " ", t)
    t = re.sub(r"(?s)<[^>]+>", " ", t)
    t = t.replace("&nbsp;", " ").replace("&amp;", "&").replace("&aacute;", "á")
    return re.sub(r"\s+", " ", t)

def extract_block(c, open_idx, tag="div"):
    """Extrae el bloque que empieza en open_idx contando anidamiento real.
    No cierra por el primer </section>: las fichas usan <div>."""
    pat = re.compile(r"<(/?)%s\b" % tag, re.I)
    depth = 0
    for m in pat.finditer(c, open_idx):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            end = c.find(">", m.end())
            return c[open_idx:end + 1]
    return c[open_idx:]

def find_block(c, class_name, tag="div"):
    m = re.search(r'<%s\b[^>]*class="[^"]*\b%s\b[^"]*"' % (tag, re.escape(class_name)), c, re.I)
    if not m:
        return None
    return extract_block(c, m.start(), tag)

# ---------------------------------------------------------------- fechas

def easter(year):
    a = year % 19
    b, c_ = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c_, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return datetime.date(year, month, day + 1)

# autovalidación del algoritmo antes de usarlo
_KNOWN = {2020: (4, 12), 2023: (4, 9), 2024: (3, 31), 2025: (4, 20),
          2026: (4, 5), 2027: (3, 28), 2028: (4, 16)}
for _y, (_m, _d) in _KNOWN.items():
    assert easter(_y) == datetime.date(_y, _m, _d), "Gauss falla en %d" % _y

MESES = {"enero":1,"febrero":2,"marzo":3,"abril":4,"mayo":5,"junio":6,"julio":7,
         "agosto":8,"septiembre":9,"setiembre":9,"octubre":10,"noviembre":11,"diciembre":12}
DIAS = {"lunes":0,"martes":1,"miercoles":2,"jueves":3,"viernes":4,"sabado":5,"domingo":6}

LITURGICAS = {
    "viernes de dolores": -9, "viernes de pasion": -9,
    "sabado de pasion": -8, "domingo de ramos": -7,
    "lunes santo": -6, "martes santo": -5, "miercoles santo": -4,
    "jueves santo": -3, "viernes santo": -2, "sabado santo": -1,
    "sabado de gloria": -1, "domingo de resurreccion": 0, "domingo de pascua": 0,
}

# ---------------------------------------------------------------- léxico

PROHIBIDO = ["tapiz","sinfonía","destila","fascinante","majestuosidad","encarna",
"resuenan","palpable","imprescindible","sin igual","no tiene equivalente",
"difícil de describir","única en el mundo","no se improvisa","funciona como",
"actúa como","no es solo","no solo es","va mucho más allá","sobrecogedor",
"sepulcral","irrepetible","epopeya","vertebra","se erige","constituye un",
"majestuosa","inabarcable","fastuosidad","atávico","apoteósica","soberbia",
"eriza la piel","deja sin palabras","legado vivo","se entretejen","dialoga con",
"inmenso escenario","meras estatuas","simbiosis perfecta","sin precedentes",
"belleza única","no tiene paralelo","paraliza el tiempo","último aliento"]

ORDENES = [r"\bRespeta\b", r"\bRespete\b", r"\bMantén\b", r"\bMantenga\b", r"\bEvita\b",
           r"\bEvite\b", r"\bNo cruces\b", r"\bno cruces\b", r"\bDebes\b", r"\bdebes\b",
           r"\bProcura\b", r"\bAbsténte\b", r"\bAbstente\b", r"\bGuarda\b", r"\bPermanece\b",
           r"\bNo te\b", r"\bNo uses\b", r"\bNo hagas\b", r"\bSigue las\b", r"\bRecuerda\b",
           r"\bten en cuenta\b", r"\bTen en cuenta\b", r"\bno olvides\b", r"\bNo olvides\b",
           r"\bconviene que\b", r"\bse ruega\b", r"\bSe ruega\b", r"\bno está permitido\b",
           # prohibiciones impersonales: no son imperativos y se colaban
           r"\bno se toca", r"\bno se cruza", r"\btampoco se cruza", r"\btampoco se toca",
           r"\bno se pisa", r"\bno se entra", r"\bestá prohibido", r"\bno está permitido",
           r"\bNo tocar", r"\bno interferir", r"\bes la norma\b", r"\bhay que respetar\b",
           # imperativos que se colaron en León y Cáceres pasando el filtro
           r"\bAdapta\b", r"\bAsume\b", r"\bConsulta\b", r"\bLlega con\b",
           r"\bSit[úu]ate\b", r"\bPrioriza\b", r"\bPlanifica\b", r"\bCalza\b"]

# Fichas de ruta. La skill dice que las rutas temáticas son colecciones
# editoriales y se montan aparte, así que los recuentos escritos para la ficha
# de una sola fiesta no les aplican: llevan una tarjeta y una pregunta por
# localidad. Se les exige el mínimo del estándar, no el número exacto. El
# espejado FAQ↔FAQPage sí se les sigue exigiendo igual que a las demás.
RUTAS = {"ruta-tambor-bombo.html"}

# ---------------------------------------------------------------- diagnóstico

def diag(path):
    name = os.path.basename(path)
    es_ruta = name in RUTAS
    c = load(path)
    out = []
    def add(sev, msg):
        out.append((sev, msg))

    # ---- 1. MARCADO (antes de contar nada)
    for tag in ("li", "div", "p", "ul", "section", "a"):
        op = len(re.findall(r"<%s\b" % tag, c, re.I))
        cl = len(re.findall(r"</%s>" % tag, c, re.I))
        if op != cl:
            add("MARCADO", "<%s> abiertos %d / cerrados %d (descuadre %+d)" % (tag, op, cl, op - cl))
    if c.count("</head>") != 1:
        add("MARCADO", "</head> aparece %d veces" % c.count("</head>"))
    if c.lower().count("<h1") != 1:
        add("MARCADO", "H1 aparece %d veces" % c.lower().count("<h1"))

    # ---- 2. JSON-LD
    bloques = re.findall(r'(?is)<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>', c)
    tipos, jsons = [], []
    for b in bloques:
        try:
            d = json.loads(b)
            jsons.append(d)
            t = d.get("@type", "?")
            tipos.append(t if isinstance(t, str) else "/".join(t))
        except Exception as e:
            add("JSONLD", "bloque no es JSON válido: %s" % e)
    add("INFO", "JSON-LD: %d bloques %s" % (len(bloques), tipos))
    for req in ("BreadcrumbList", "FAQPage"):
        if not any(req in t for t in tipos):
            add("JSONLD", "falta bloque %s" % req)
    if not any(t not in ("BreadcrumbList", "FAQPage") for t in tipos):
        add("JSONLD", "falta el bloque de evento (Festival/EventSeries/…)")
    if "eventSchedule" in c:
        add("JSONLD", "aparece eventSchedule — prohibido")

    # ---- 3. FECHAS
    sd = re.findall(r'"startDate"\s*:\s*"([^"]+)"', c)
    ed = re.findall(r'"endDate"\s*:\s*"([^"]+)"', c)
    hoy = datetime.date.today()
    anio_ed = None
    for s in sd:
        try:
            f = datetime.date.fromisoformat(s[:10])
        except ValueError:
            add("FECHAS", "startDate no parseable: %r" % s); continue
        anio_ed = anio_ed or f.year
        # Una edición en curso tiene startDate en el pasado y es correcto: la
        # norma dice que la edición vigente no cambia hasta el día siguiente de
        # que termine. Solo avisamos si TAMBIÉN ha pasado el endDate.
        if f < hoy:
            fin = None
            if ed:
                try:
                    fin = datetime.date.fromisoformat(ed[0][:10])
                except ValueError:
                    fin = None
            if fin is None or fin < hoy:
                add("FECHAS", "startDate %s ya ha pasado" % s[:10])
    add("INFO", "startDate %s · endDate %s" % (sd, ed))

    # rango visible en ficha-datos-clave vs JSON-LD
    dk = find_block(c, "ficha-datos-clave")
    if dk:
        tv = visible_text(dk)
        rango = re.findall(r"(\d{1,2})(?:\s+de\s+(\w+))?\s*(?:al|a|-|–)\s*(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?", tv, re.I)
        add("INFO", "datos-clave visible: %s" % tv[:220])
        if sd and ed and rango:
            # Una fiesta repartida en dos fines de semana («27-29 de agosto y
            # 3-5 de septiembre») deja dos rangos visibles y un solo Festival
            # que los abarca: el inicio es el del primer rango y el fin, el del
            # último. Comparar solo el primero daba falso positivo.
            r = rango[0]
            rf = rango[-1]
            mes_fin = MESES.get(strip_accents(rf[3].lower()))
            mes_ini = MESES.get(strip_accents((r[1] or r[3]).lower()))
            anio = int(r[4]) if r[4] else (anio_ed or hoy.year)
            anio_fin = int(rf[4]) if rf[4] else anio
            try:
                vi = datetime.date(anio, mes_ini, int(r[0]))
                vf = datetime.date(anio_fin, mes_fin, int(rf[2]))
                if str(vi) != sd[0][:10] or str(vf) != ed[0][:10]:
                    add("FECHAS", "rango visible %s→%s NO coincide con JSON-LD %s→%s"
                        % (vi, vf, sd[0][:10], ed[0][:10]))
            except Exception as e:
                add("FECHAS", "no se pudo comparar el rango visible (%s)" % e)
    else:
        add("BLOQUES", "no se encuentra ficha-datos-clave")

    # etiquetas litúrgicas con fecha PEGADA a la etiqueta
    txt = visible_text(c)
    plano = strip_accents(txt.lower())
    anio_ref = anio_ed or hoy.year
    pas = easter(anio_ref)
    for etiqueta, off in LITURGICAS.items():
        correcta = pas + datetime.timedelta(days=off)
        for m in re.finditer(re.escape(etiqueta), plano):
            ven = plano[m.end():m.end() + 45]
            pre = plano[max(0, m.start() - 45):m.start()]
            # Si la etiqueta va entre paréntesis, la fecha a la que se refiere
            # es la de ANTES: «del 19 de marzo (Viernes de Dolores) al 28 de
            # marzo». Mirar hacia delante ahí agarra la fecha del otro extremo.
            entre_parentesis = pre.rstrip().endswith("(") and ven.lstrip().startswith(")")
            adelante = re.match(r"[^\d]{0,12}(\d{1,2})\s+de\s+([a-z]+)", ven)
            atras = re.search(r"(\d{1,2})\s+de\s+([a-z]+)[^\d]{0,12}$", pre)
            mm = (atras or adelante) if entre_parentesis else (adelante or atras)
            if not mm:
                continue
            mes = MESES.get(mm.group(2))
            if not mes:
                continue
            try:
                hallada = datetime.date(anio_ref, mes, int(mm.group(1)))
            except ValueError:
                continue
            if hallada != correcta:
                add("FECHAS", "«%s» con fecha %s — según Pascua %s de %d debería ser %s"
                    % (etiqueta, hallada, pas, anio_ref, correcta))

    # nombre de día vs fecha real
    for m in re.finditer(r"(lunes|martes|mi[eé]rcoles|jueves|viernes|s[áa]bado|domingo)\s+(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?", txt, re.I):
        dia = DIAS.get(strip_accents(m.group(1).lower()))
        mes = MESES.get(strip_accents(m.group(3).lower()))
        anio = int(m.group(4)) if m.group(4) else anio_ref
        if mes is None:
            continue
        try:
            f = datetime.date(anio, mes, int(m.group(2)))
        except ValueError:
            continue
        if f.weekday() != dia:
            add("FECHAS", "«%s» pero el %s fue %s" % (m.group(0), f,
                list(DIAS)[f.weekday()]))

    # ---- 4. METADATOS
    t = re.search(r"(?is)<title>(.*?)</title>", c)
    if t:
        tt = t.group(1).strip()
        add("INFO", "title (%d): %s" % (len(tt), tt))
        if not 50 <= len(tt) <= 65:
            add("META", "title fuera de 50-65 (%d)" % len(tt))
    md = re.search(r'(?is)<meta\s+name="description"\s+content="([^"]*)"', c)
    ogt = re.search(r'(?is)<meta\s+property="og:title"\s+content="([^"]*)"', c)
    ogd = re.search(r'(?is)<meta\s+property="og:description"\s+content="([^"]*)"', c)
    if md:
        add("INFO", "meta (%d): %s" % (len(md.group(1)), md.group(1)))
        if not 110 <= len(md.group(1)) <= 165:
            add("META", "meta description fuera de 110-165 (%d)" % len(md.group(1)))
    if ogt and t and ogt.group(1).strip() == t.group(1).strip():
        add("META", "og:title idéntico al title")
    if ogd and md and ogd.group(1).strip() == md.group(1).strip():
        add("META", "og:description idéntica a la meta")
    can = re.search(r'(?is)<link\s+rel="canonical"[^>]*href="([^"]*)"', c)
    if not can:
        add("META", "sin rel=canonical")
    elif name not in can.group(1):
        add("META", "canonical apunta a %s (archivo %s)" % (can.group(1), name))

    # año de edición en sitios prohibidos
    anio_txt = str(anio_ref)
    zonas = {"title": t.group(1) if t else "",
             "meta": md.group(1) if md else "",
             "og:title": ogt.group(1) if ogt else "",
             "og:description": ogd.group(1) if ogd else ""}
    h1 = re.search(r"(?is)<h1[^>]*>(.*?)</h1>", c)
    zonas["h1"] = visible_text(h1.group(1)) if h1 else ""
    foot = re.search(r"(?is)<footer.*?</footer>", c)
    zonas["footer"] = visible_text(foot.group(0)) if foot else ""
    # Lo prohibido es el año DE LA EDICIÓN, que caduca. Los años históricos
    # («ITI 2015», «UNESCO desde 2020», «BIC 2024») se quedan por norma, y son
    # siempre anteriores al de la edición vigente.
    for z, v in zonas.items():
        for a in re.findall(r"\b(20\d{2})\b", v):
            if int(a) >= int(anio_ref):
                add("META", "año de la edición (%s) en %s: %s" % (a, z, v.strip()[:110]))
                break

    # ---- 5. BLOQUES
    av = find_block(c, "aviso-sensibilidad")
    if not av:
        add("BLOQUES", "sin aviso-sensibilidad")
    else:
        lis = re.findall(r"(?is)<li\b[^>]*>(.*?)</li>", av)
        if len(lis) != 3:
            add("BLOQUES", "aviso-sensibilidad con %d puntos (deben ser 3)" % len(lis))
        if re.search(r"(?is)<li\b[^>]*>.*?<strong", av):
            add("BLOQUES", "aviso-sensibilidad con <strong> dentro de <li>")
        for i, li in enumerate(lis, 1):
            vt = visible_text(li)
            for pat in ORDENES:
                if re.search(pat, vt):
                    add("BLOQUES", "aviso punto %d posible orden al visitante (%s): %s"
                        % (i, pat, vt[:140]))
                    break
        add("INFO", "AVISO: " + " || ".join(visible_text(l)[:110] for l in lis))

    if "music-block" not in c:
        add("BLOQUES", "sin music-block")
    ms = len(re.findall(r'class="[^"]*\bmust-see-card\b', c))
    det = len(re.findall(r"<details\b", c))
    if es_ruta:
        if ms < 4:
            add("BLOQUES", "must-see-card: %d (ficha de ruta, mínimo 4)" % ms)
    elif ms != 4:
        add("BLOQUES", "must-see-card: %d (deben ser 4)" % ms)
    if det < ms:
        add("BLOQUES", "must-see con menos <details> (%d) que tarjetas (%d)" % (det, ms))

    faq_blk = find_block(c, "faq", "dl") or find_block(c, "faq") or ""
    preg_body = [visible_text(x).strip() for x in re.findall(r"(?is)<dt\b[^>]*>(.*?)</dt>", faq_blk)]
    if not preg_body:
        preg_body = [visible_text(x).strip() for x in re.findall(r"(?is)<h3\b[^>]*>(\s*¿.*?)</h3>", faq_blk)]
    faq_ld_q = []
    for d in jsons:
        if "FAQPage" in str(d.get("@type", "")):
            faq_ld_q = [q.get("name", "") for q in d.get("mainEntity", [])]
    if es_ruta:
        if len(faq_ld_q) < 5:
            add("BLOQUES", "FAQPage con %d preguntas (ficha de ruta, mínimo 5)" % len(faq_ld_q))
        if len(preg_body) < 5:
            add("BLOQUES", "FAQ en el cuerpo con %d preguntas (ficha de ruta, mínimo 5)" % len(preg_body))
    else:
        if len(faq_ld_q) != 5:
            add("BLOQUES", "FAQPage con %d preguntas (deben ser 5)" % len(faq_ld_q))
        if len(preg_body) != 5:
            add("BLOQUES", "FAQ en el cuerpo con %d preguntas (deben ser 5)" % len(preg_body))
    for q in preg_body:
        if q not in faq_ld_q:
            add("BLOQUES", "pregunta del cuerpo ausente del FAQPage: %s" % q[:90])
    for q in faq_ld_q:
        if q not in preg_body:
            add("BLOQUES", "pregunta del FAQPage ausente del cuerpo: %s" % q[:90])

    # Las dos capas de la FAQ (cuerpo y FAQPage) tienen que dar la MISMA
    # respuesta. En Zaragoza daban respuestas distintas en dos preguntas, y eso
    # no lo veía nadie porque el JSON-LD no se lee en pantalla.
    def norm(t):
        t = visible_text(t).replace("«", '"').replace("»", '"')
        return re.sub(r"\s+", " ", t).strip().strip('"').rstrip(".")
    # Una capa puede estar resumida; lo que no puede es decir OTRA cosa. Se
    # comparan los datos duros (cifras y nombres propios) y el tamaño.
    def duros(t):
        return set(re.findall(r"\d[\d.,:]*", t)) | {
            w for w in re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]{3,}", t)
            if w not in ("Procesión", "Semana", "Santa", "Santo", "Jueves",
                         "Viernes", "Miércoles", "Martes", "Lunes", "Domingo",
                         "Sábado", "Para", "Desde", "Todas", "Todos", "Cada")}
    pares_body = re.findall(r"(?is)<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>", faq_blk)
    resp_body = {norm(q): norm(a) for q, a in pares_body}
    for d in jsons:
        if "FAQPage" not in str(d.get("@type", "")):
            continue
        for q in d.get("mainEntity", []):
            qn = norm(q.get("name", ""))
            ld = norm(q.get("acceptedAnswer", {}).get("text", ""))
            if qn not in resp_body:
                continue
            cu = resp_body[qn]
            dif = duros(cu) ^ duros(ld)
            corto = min(len(cu), len(ld)) / max(len(cu), len(ld), 1)
            # Va a ESTILO y no a AVISO: una capa resumida es legítima y la
            # referencia (Orihuela) las tiene. Lo que hay que leer en contexto
            # es si la diferencia es un resumen o una respuesta distinta.
            if dif:
                add("ESTILO", "cuerpo y FAQPage no coinciden en «%s»: %s"
                    % (qn[:50], ", ".join(sorted(dif))[:80]))
            elif corto < 0.6:
                add("ESTILO", "cuerpo y FAQPage de tamaño muy distinto en «%s»" % qn[:50])

    fest = find_block(c, "festero", "dl")
    if not fest:
        add("BLOQUES", "sin dl.festero")
    else:
        n = len(re.findall(r"<dt\b", fest))
        if not 4 <= n <= 9:
            add("BLOQUES", "vocabulario con %d términos (4-9)" % n)
        add("INFO", "vocabulario: %d términos" % n)

    et = len(re.findall(r'class="etiqueta', c))
    if et != 9:
        add("BLOQUES", "etiquetas: %d (deben ser 9)" % et)
    dest = len(re.findall(r'class="etiqueta destacada"', c))
    if dest != 2:
        add("BLOQUES", "etiquetas destacadas: %d (deben ser 2)" % dest)
    if "etiqueta-destacada" in c:
        add("BLOQUES", "grafía etiqueta-destacada (debe ser «etiqueta destacada»)")

    rel = re.findall(r'(?is)<a\b[^>]*class="[^"]*\b(?:ficha-rel-card|relacionada-card)\b[^"]*"[^>]*href="([^"]+)"', c)
    if not rel:
        rel = [h for h in re.findall(r'(?is)<a\b[^>]*href="([^"]+\.html)"[^>]*class="[^"]*rel', c)]
    rel = [r for r in rel if "index.html" not in r]
    if len(rel) != 3:
        add("BLOQUES", "relacionadas: %d (deben ser 3) %s" % (len(rel), rel))

    if not re.search(r'(?is)class="[^"]*galeria[^"]*"[^>]*style="[^"]*display:\s*none', c) \
       and not re.search(r'(?is)<div[^>]*style="[^"]*display:\s*none[^"]*"[^>]*class="[^"]*galeria', c):
        if "galeria" in c:
            add("BLOQUES", "galería sin display:none evidente")
    if "back-link" not in c:
        add("BLOQUES", "sin back-link")

    # ---- 6. INTEGRIDAD DE ENLACES E IMÁGENES
    d = os.path.dirname(os.path.abspath(path))
    for h in set(re.findall(r'href="([^":#?]+\.html)"', c)):
        if not os.path.exists(os.path.join(d, h)):
            add("INTEGRIDAD", "enlace roto: %s" % h)
    gal = find_block(c, "galeria") or ""
    for s in set(re.findall(r'src="(images/[^"]+)"', c)):
        if s in gal:
            continue
        if not os.path.exists(os.path.join(d, s)):
            add("INTEGRIDAD", "imagen visible inexistente: %s" % s)

    # ---- 7. LÉXICO (solo se reporta, nunca se reemplaza en lote)
    # Excepciones por homonimia: la palabra prohibida es la figurada, pero la
    # misma raíz tiene usos normales en español que no son el patrón de IA.
    # «encarnar un personaje» es lo que hace un figurante; «encarna la
    # identidad» es la inflación que se prohíbe. Lo mismo con el Paso Encarnado
    # de Lorca o Nuestra Señora de la Encarnación.
    # «encarna» prohibido es el figurado («encarna la identidad»). No lo son:
    # el Paso Encarnado de Lorca, Nuestra Señora de la Encarnación, ni
    # «encarnar a» un personaje, que es lo que hace un figurante.
    # «destila» prohibido es el figurado. Los «destilados» de la cuerva de
    # Águilas son bebida.
    FORMAS = {
        "encarna": (r"\bencarna(?:n|ba|ban|ron|r|ndo)?\b"
                    r"(?!\s+(?:a|al)\b|\s+(?:su|el|la|un|una)\s+"
                    r"(?:personaje|papel|figura|pap))"),
        "destila": r"\bdestila(?:n|ba|ban|ndo)?\b",
    }
    for w in PROHIBIDO:
        patron = FORMAS.get(w.lower()) or re.escape(w)
        for m in re.finditer(patron, txt, re.I):
            ctx = txt[max(0, m.start() - 55):m.end() + 55]
            add("LEXICO", "«%s» → …%s…" % (w, ctx))

    # ---- 8. ESTILO — pasos 11 y 12 del protocolo.
    # No cuenta para el total de avisos: son hallazgos para leer en contexto,
    # no fallos automáticos. Así la calibración de Orihuela sigue siendo 0.
    ciudad = re.sub(r"^(semana-santa|carnaval|moros-cristianos|fiesta)-", "",
                    name.replace(".html", "")).replace("-", " ")

    # La esencia: apertura y extensión
    mh = re.search(r'(?is)<h2[^>]*>[^<]*esencia[^<]*</h2>(.*?)<h2', c)
    if mh:
        ese = visible_text(mh.group(1)).strip()
        n_ese = len(ese.split())
        add("INFO", "La esencia: %d palabras" % n_ese)
        if not 60 <= n_ese <= 95:
            add("ESTILO", "La esencia con %d palabras (norma 60-90)" % n_ese)
        primera = re.split(r"(?<=[.!?])\s", ese)[0] if ese else ""
        pl = strip_accents(primera.lower())
        if ciudad and strip_accents(ciudad.lower()).split()[0] in pl:
            add("ESTILO", "La esencia abre nombrando la ciudad: «%s»" % primera[:110])
        for olor in ("azahar", "incienso", "cera", "polvora", "vino", "tierra mojada", "huele", "olor", "aroma"):
            if olor in pl:
                add("ESTILO", "La esencia abre con olor («%s»): «%s»" % (olor, primera[:100]))
                break
        for cli in ("te transporta", "retrocede siglos", "el tiempo se detiene",
                    "viajar al pasado", "como si el tiempo"):
            if cli in pl:
                add("ESTILO", "La esencia abre con cliché temporal: «%s»" % primera[:100])
                break

    # Bloque ¿En qué consiste? — norma del 28-10-2026
    iq = c.find('id="que-es"')
    if iq < 0:
        add("ESTILO", 'sin ancla id="que-es" en el h2 del bloque')
    else:
        fin = c.find("<h2", iq + 10)
        nota = c.find('<p class="nota-grid">', iq)
        if 0 < nota < fin:
            fin = nota
        blk = c[iq:fin]
        nq = len(visible_text(blk).split())
        npar = len(re.findall(r"<p\b", blk))
        add("INFO", "¿En qué consiste?: %d palabras, %d párrafos" % (nq, npar))
        if not 350 <= nq <= 470:
            add("ESTILO", "¿En qué consiste? con %d palabras (norma 350-450)" % nq)
        if npar != 4:
            add("ESTILO", "¿En qué consiste? con %d párrafos (deben ser 4)" % npar)

    # Patrones del humanizer que la lista de léxico no atrapa
    ESTILO_PAT = [
        (r"\bact[úu]a (?:como|de)\b", "copula avoidance"),
        (r"\bse erige\b|\bconstituye un\b|\bfunciona como\b", "copula avoidance"),
        (r"no es (?:solo |solamente |\w+ )?[^.]{3,70}?\bsino\b", "negativo paralelo X-no-Y"),
        (r"\bno [a-záéíóúñ]+: [a-záéíóúñ]+", "negativo paralelo con dos puntos"),
        (r", no (?:al lado|a su lado|su borde|el recinto|un espectáculo|el protagonista)\b", "X-no-Y de cierre"),
        (r"\bning[úu]n otro\b|\bning[úu]na otra\b|\bno tiene (?:r[ée]plica|equivalente|paralelo)\b",
         "exclusividad sin fuente"),
        (r"\bsolo se entiende\b|\bsolo existe en\b|\b[úu]nic[oa] en el mundo\b",
         "exclusividad sin fuente"),
        (r"\bno hay otr[oa]\b|\ben cualquier lugar del mundo\b|\bno se parece a nada\b|\bcompletamente [úu]nic[oa]\b|\b[úu]nic[oa]s? en (?:Espa[ñn]a|Europa)\b",
         "exclusividad sin fuente"),
        (r"\bla capital de (?:la|el) \w+ \w*espa[ñn]ola?\b|\bel referente \w+ de Espa[ñn]a\b",
         "superlativo territorial"),
        (r"\bimpresionantes?\b|\babrumadoras?\b|\besencia pura\b|\bcolosal(?:es)?\b|\bespectacularidad\b",
         "inflación de importancia"),
        (r"\bel momento m[áa]s esperado\b|\bla imagen m[áa]s venerada\b",
         "superlativo sin fuente"),
        (r"(?<!¿)\bmerecen? la pena\b|\bno aparecen? en las gu[íi]as\b|\bhay que verlo\b",
         "lenguaje de folleto"),
        (r"\b(?:marcando|destacando|reflejando|potenciando|inaugurando|subrayando|simbolizando)\b",
         "gerundio de profundidad falsa"),
        (r"\binmens[oa]\b|\bfen[óo]meno en s[íi]\b|\bmarca un hito\b|\btrasciende\b",
         "inflación de importancia"),
        (r"\bm[áa]s (?:antigua|solemne|impresionante|emblem[áa]tic[oa]s?|important[es]*|caracter[íi]stic[oa]s?) (?:de|del) (?:toda |la |España|Europa|Extremadura|Castilla)",
         "superlativo territorial"),
        # Zaragoza traía estos y ninguna plantilla los veía.
        (r"\buno de los \w+ m[áa]s\b|\buna de las \w+ m[áa]s\b",
         "superlativo de folleto"),
        (r"\bcentro absoluto\b|\bmomento cumbre\b|\bplena intensidad\b|\bcinematogr[áa]fic[oa]s?\b|\bpunto [áa]lgido\b",
         "inflación de importancia"),
        (r"\b(?:percusi[óo]n|emoci[óo]n|devoci[óo]n|tradici[óo]n|silencio) pur[oa]\b",
         "lenguaje de folleto"),
        (r"\bininterrumpid[oa]s? m[áa]s antigu[oa]\b|\bm[áa]s singulares? de\b",
         "superlativo sin fuente"),
    ]
    for pat, etiq in ESTILO_PAT:
        for m in re.finditer(pat, txt, re.I):
            add("ESTILO", "%s → …%s…" % (etiq, txt[max(0, m.start() - 50):m.end() + 50]))

    # Anti-repetición de CIFRAS: el mismo número contado en dos bloques es el
    # caso típico de incoherencia (duración, número de pasos, de cofradías).
    # Las frases repetidas se miden más abajo, filtrando los nombres propios.
    bloques = re.split(r"(?is)<h2[^>]*>", c)
    titulos = ["cabecera"] + [visible_text(b.split("</h2>")[0]).strip()[:28]
                              for b in bloques[1:]]
    donde = {}
    for ti, b in zip(titulos, bloques):
        vb = visible_text(b)
        for m in re.finditer(r"\b(\d{1,3}(?:\.\d{3})?)\s+(cofrad|hermandad|paso|procesi|d[íi]as?|bracero|papon|costaler|estacion|desfil)", vb, re.I):
            clave = "%s %s" % (m.group(1), m.group(2).lower())
            donde.setdefault(clave, set()).add(ti)
    for clave, tits in sorted(donde.items()):
        if len(tits) > 1:
            add("ESTILO", "cifra «%s» repetida en %d bloques: %s"
                % (clave, len(tits), " · ".join(sorted(tits))))

    # Anti-repetición de FRASES: la misma secuencia de 7 palabras en dos
    # bloques distintos. Es lo que el barrido de cifras no ve, porque son
    # frases y no números, y es donde se escondían las cinco duplicaciones de
    # Zaragoza (el bloque de fechas calcado en la FAQ, la tarjeta repitiendo
    # ¿En qué consiste?, el listado repitiendo la tabla).
    # Se descartan las secuencias que son nombre propio (tres o más palabras
    # en mayúscula), porque las denominaciones oficiales de las corporaciones
    # tienen que repetirse tal cual.
    N = 8
    pals = {}
    for ti, b in zip(titulos, bloques):
        if ti in pals:
            continue
        pals[ti] = re.findall(r"[\wÁÉÍÓÚÜÑáéíóúüñ']+", visible_text(b))

    def ngr(ws):
        return {tuple(w.lower() for w in ws[k:k + N]) for k in range(len(ws) - N + 1)
                if sum(1 for p in ws[k:k + N] if p[:1].isupper()) < 3}

    idx = {ti: ngr(ws) for ti, ws in pals.items()}
    nombres = sorted(pals)
    hall = []
    for a in range(len(nombres)):
        for b2 in range(a + 1, len(nombres)):
            ta, tb = nombres[a], nombres[b2]
            comun = idx[ta] & idx[tb]
            if not comun:
                continue
            ws = pals[ta]
            k = 0
            while k <= len(ws) - N:
                if tuple(w.lower() for w in ws[k:k + N]) in comun:
                    fin = k + N
                    # se alarga mientras el n-grama siguiente también sea común:
                    # así una duplicación larga se informa una vez, no N veces
                    while (fin - N + 1 <= len(ws) - N
                           and tuple(w.lower() for w in ws[fin - N + 1:fin + 1]) in comun):
                        fin += 1
                    hall.append((fin - k, ta, tb, " ".join(ws[k:fin])))
                    k = fin
                else:
                    k += 1
    for largo, ta, tb, fr in sorted(hall, reverse=True)[:12]:
        add("ESTILO", "frase de %d palabras repetida en %s y %s: «%s»"
            % (largo, ta, tb, fr[:110]))

    return name, out


def main(paths):
    for p in paths:
        full = p if os.path.isabs(p) else os.path.join(REPO, p)
        name, out = diag(full)
        print("=" * 72)
        print(name)
        print("=" * 72)
        orden = ["MARCADO", "INTEGRIDAD", "JSONLD", "FECHAS", "META", "BLOQUES",
                 "LEXICO", "ESTILO", "INFO"]
        for sev in orden:
            items = [m for s, m in out if s == sev]
            if not items:
                continue
            print("\n[%s] %d" % (sev, len(items)))
            for i in items:
                print("  - " + i)
        # LEXICO no cuenta como aviso. La propia skill manda leer esa lista caso
        # por caso («nunca buscar y reemplazar en lote: casi la mitad de las
        # coincidencias son falsos positivos»), así que un aviso automático sobre
        # algo que por definición hay que leer a mano no es un aviso: es un
        # recordatorio. Pasa al nivel de ESTILO, para leer en contexto.
        problemas = [1 for s, _ in out if s not in ("INFO", "ESTILO", "LEXICO")]
        contexto = [1 for s, _ in out if s in ("ESTILO", "LEXICO")]
        print("\n>>> %d avisos (sin contar INFO) · %d hallazgos de estilo y léxico "
              "para leer en contexto\n" % (len(problemas), len(contexto)))


if __name__ == "__main__":
    main(sys.argv[1:] or ["semana-santa-orihuela.html"])
