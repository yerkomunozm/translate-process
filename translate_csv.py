#!/usr/bin/env python3
"""Traduce un CSV de subtítulos (salida de docx_to_csv.py) con la API de OpenAI.

Solo usa la librería estándar (llama a la API REST con urllib).
La API key se lee de la variable de entorno OPENAI_API_KEY o del archivo .env
(junto a este script); una variable ya definida en el entorno tiene prioridad.
Variables: OPENAI_API_KEY (obligatoria), OPENAI_MODEL, OPENAI_BASE_URL, SOURCE_LANG, TARGET_LANG.
Los argumentos de línea de comandos tienen prioridad sobre el .env.

Uso:
    # en .env:  OPENAI_API_KEY=sk-...
    python3 translate_csv.py -i output/TheWire_S1E1.csv -o output/TheWire_S1E1_es.csv \
        --target-lang "español de Chile (es-CL)" --instructions "glosario o notas opcionales"

Si el CSV de salida ya existe, se reanuda: los segmentos ya traducidos se omiten.
"""
import argparse
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_BASE_URL = "https://api.openai.com/v1"
JSON_DIR = Path(__file__).resolve().parent / "json"

SYSTEM_PROMPT = """\
Actúa como un traductor y revisor profesional de subtítulos audiovisuales, especializado en traducción del @@SOURCE@@ al **@@TARGET@@**.

Tu tarea es traducir íntegramente los segmentos que se te entreguen, respetando las siguientes instrucciones.

## 1. Fidelidad al original — Prioridad máxima

- El texto en @@SOURCE@@ es la fuente de referencia.
- Conserva con precisión todo el contenido semántico, la intención comunicativa, el registro, el tono y los matices del original.
- **No añadas, omitas, inventes ni reformules información de forma que cambie el significado.**
- No conviertas preguntas en afirmaciones ni afirmaciones en preguntas.
- Respeta las negaciones, condiciones, cantidades, nombres propios, referencias temporales y relaciones entre los personajes.
- Conserva las repeticiones cuando tengan una función expresiva o narrativa.
- No suavices automáticamente las groserías, los insultos ni el lenguaje coloquial.
- No interpretes información ambigua como si fuera un hecho confirmado.
- No completes frases con información que el original no proporciona.
- Solo se permiten omisiones o reformulaciones mínimas cuando sean necesarias para lograr una redacción natural en @@TARGET@@ o respetar las restricciones de subtitulado, sin perder información esencial.
- Si una frase continúa en el segmento siguiente, considera ambos segmentos para comprenderla, pero conserva la correspondencia exacta entre el contenido y su segmento original.

**Una traducción fluida pero semánticamente incorrecta nunca debe considerarse aceptable.**

## 2. Variante lingüística: @@TARGET@@

- Utiliza @@TARGET@@ natural, idiomático y gramaticalmente correcto.
- Mantén un grado moderado de localización propia de esta variante para que el resultado también sea comprensible para un público latinoamericano amplio.
- Evita modismos regionales excesivamente marcados cuando no estén justificados por el contexto.
- Utiliza terminología precisa y consistente según el tema: deporte, tecnología, policía, derecho, música, cultura, etc.
- Evita calcos del @@SOURCE@@, traducciones literales artificiales y expresiones que no resulten naturales en @@TARGET@@.
- Conserva el nivel de formalidad, cercanía, agresividad o informalidad del original.
- Respeta los nombres propios, títulos y denominaciones oficiales.

## 3. Reglas obligatorias de subtitulado

**Extensión:**
- Máximo 2 líneas por segmento.
- Máximo 42 caracteres por línea, contando espacios y signos de puntuación.
- Cuando el contenido pueda expresarse naturalmente en una sola línea, utiliza una sola línea.

**Formato pirámide:**
- En los subtítulos de dos líneas, la primera línea debe ser igual o más corta que la segunda.
- Prioriza una segunda línea más larga cuando sea posible.
- Se permite una excepción si el formato pirámide provoca una ruptura sintáctica incorrecta, afecta la comprensión o altera el sentido.
- No fuerces divisiones antinaturales solo para conseguir una distribución visual determinada.

**Segmentación:**
- Divide las líneas en puntos sintácticamente naturales.
- Mantén juntos los grupos de palabras que forman una unidad de significado.
- Evita separar artículos de sustantivos, preposiciones de sus complementos y otras construcciones estrechamente relacionadas.
- Respeta el orden y los límites de los segmentos. No fusiones segmentos, no desplaces información entre ellos y no modifiques sus id.

**Diálogos:**
- Cuando dos personajes hablan en un mismo subtítulo, utiliza un guion corto seguido de un espacio (`- `) al comienzo de cada intervención.
- Cada hablante debe ocupar su propia línea.
- En estos casos, la separación de hablantes tiene prioridad sobre el formato pirámide.
- Mantén las acotaciones, la cursiva y demás convenciones de subtitulado cuando correspondan.

## 4. Procedimiento de traducción

Para cada segmento:

1. Lee el texto original en @@SOURCE@@.
2. Considera el contexto proporcionado por los segmentos anteriores y posteriores.
3. Determina el significado exacto, la intención del hablante y el registro.
4. Formula una traducción natural al @@TARGET@@.
5. Comprueba que no se haya añadido, omitido ni modificado información.
6. Verifica la modalidad de cada oración: interrogativa, afirmativa, negativa, exclamativa, condicional, etc.
7. Comprueba la coherencia terminológica y la continuidad entre segmentos.
8. Ajusta la división de líneas y verifica los límites de caracteres.
9. Realiza una última comparación con el original en @@SOURCE@@ para detectar errores de fidelidad.

## 5. Etiquetas y formato estructural

- Respeta las etiquetas de formato presentes en el original, como `<i>...</i>`, y determina su función.
- No inventes ni elimines etiquetas estructurales.
- Nunca sacrifiques contenido ni alteres el significado para acomodar una etiqueta.

## 6. Prioridad ante conflictos

Si alguna regla formal (longitud, pirámide, etc.) entra en conflicto con la fidelidad al significado, **prioriza la fidelidad semántica** y evita alterar el sentido solo para cumplir una restricción formal.

## 7. Formato de entrada y salida

- Recibirás un JSON con "context" (segmentos previos ya traducidos, solo referencia), "segments" (los que debes traducir, cada uno con "id" y "text") y "following" (textos originales en @@SOURCE@@ de los segmentos siguientes, solo referencia).
- Devuelve exactamente una traducción por cada elemento de "segments", con el mismo "id". No traduzcas "context" ni "following".
- En "text" va únicamente la traducción lista para copiar, con los saltos de línea como "\\n". Sin notas, explicaciones, comillas añadidas ni asteriscos.
"""

RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "translations",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "translations": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "text": {"type": "string"},
                        },
                        "required": ["id", "text"],
                        "additionalProperties": False,
                    },
                }
            },
            "required": ["translations"],
            "additionalProperties": False,
        },
    },
}


def call_openai(api_key, model, system, user, retries=5):
    """Llama a Chat Completions con reintentos y backoff ante 429/5xx/red."""
    body = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": RESPONSE_SCHEMA,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL).rstrip("/") + "/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
    )
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.load(resp)
            return json.loads(data["choices"][0]["message"]["content"])["translations"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            if e.code not in (408, 409, 429, 500, 502, 503, 504) or attempt == retries:
                raise RuntimeError(f"OpenAI HTTP {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError):
            if attempt == retries:
                raise
        wait = min(2 ** attempt, 30)
        print(f"  reintento {attempt}/{retries - 1} en {wait}s...", file=sys.stderr)
        time.sleep(wait)


def translate_batch(api_key, model, system, context, batch, following=()):
    """Traduce un lote y valida que vuelvan exactamente los mismos ids."""
    payload = {
        "context": [{"id": r["segment_no"], "text": r["source"], "translation": r["target"]} for r in context],
        "segments": [{"id": r["segment_no"], "text": r["source"]} for r in batch],
        "following": [r["source"] for r in following],
    }
    user = json.dumps(payload, ensure_ascii=False)
    expected = [r["segment_no"] for r in batch]
    # Si el modelo devuelve ids incorrectos, se reintenta el lote completo.
    for attempt in range(1, 4):
        out = call_openai(api_key, model, system, user)
        got = {t["id"]: t["text"] for t in out}
        if set(got) == set(expected) and len(out) == len(expected):
            return [got[i] for i in expected]
        print(f"  respuesta con ids inconsistentes (intento {attempt}/3)", file=sys.stderr)
    raise RuntimeError(f"El modelo no devolvió los ids esperados para el lote {expected[0]}..{expected[-1]}")


def check_format(text, max_lines=2, max_chars=42):
    """Avisos de formato de subtitulado (no corrige; solo informa)."""
    lines = text.split("\n")
    warnings = []
    if len(lines) > max_lines:
        warnings.append(f"{len(lines)} líneas (máx. {max_lines})")
    for ln in lines:
        if len(ln) > max_chars:
            warnings.append(f"línea de {len(ln)} caracteres (máx. {max_chars}): {ln!r}")
    return warnings


def read_rows(path, source_col):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        if source_col not in (reader.fieldnames or []):
            sys.exit(f"El CSV no tiene la columna '{source_col}'. Columnas: {reader.fieldnames}")
        return [
            {"segment_no": r["segment_no"], "source": r[source_col]}
            for r in reader
        ]


def load_done(path, target_col):
    """Segmentos ya traducidos en un CSV de salida previo (para reanudar)."""
    if not path.exists():
        return {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        return {r["segment_no"]: r[target_col] for r in csv.DictReader(f) if r.get(target_col)}


def seg_id(value):
    """Id numérico si es posible (como en el formato de ejemplo)."""
    return int(value) if str(value).strip().isdigit() else value


def write_json(path, rows, input_path, target_lang):
    """Escribe la traducción en JSON (carpeta json/): original = salida del modelo, review = copia inicial."""
    m = re.search(r"\(([^)]+)\)", target_lang)
    ids = [seg_id(r["segment_no"]) for r in rows]
    doc = {
        "document_title": f"{input_path.stem} · {len(rows)} segmentos · traducción {m.group(1) if m else target_lang}",
        "source_artifact": input_path.name,
        "language": m.group(1) if m else target_lang,
        "range": [ids[0], ids[-1]] if ids else [],
        "segment_count": len(rows),
        "confirmed_by_script": False,
        "segments": [
            {
                "id": seg_id(r["segment_no"]),
                "source": r["source"],
                "original": r["target"],
                "review": r["target"],
                "status": "unchanged",
            }
            for r in rows
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_dotenv(path):
    """Carga KEY=VALUE de un .env sin pisar variables ya definidas en el entorno."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip("\"'")
        if value:
            os.environ.setdefault(key.strip(), value)


def main():
    load_dotenv(Path(__file__).resolve().parent / ".env")  # antes del parser: aporta los defaults
    env = os.environ.get
    p = argparse.ArgumentParser(description="Traduce un CSV de subtítulos con la API de OpenAI.")
    p.add_argument("-i", "--input", required=True, type=Path, help="CSV de entrada (segment_no,source_en)")
    p.add_argument("-o", "--output", required=True, type=Path, help="CSV de salida")
    p.add_argument("--source-lang", default=env("SOURCE_LANG", "inglés estadounidense"), help="idioma origen (env SOURCE_LANG; default: inglés estadounidense)")
    p.add_argument("--target-lang", default=env("TARGET_LANG", "español de Chile (es-CL)"), help="idioma destino (env TARGET_LANG; default: español de Chile (es-CL))")
    p.add_argument("--source-col", default="source_en", help="columna a traducir (default: source_en)")
    p.add_argument("--model", default=env("OPENAI_MODEL", "gpt-4o"), help="modelo de OpenAI (env OPENAI_MODEL; default: gpt-4o)")
    p.add_argument("--batch-size", type=int, default=30, help="segmentos por llamada (default: 30)")
    p.add_argument("--context", type=int, default=5, help="segmentos previos como contexto (default: 5)")
    p.add_argument("--lookahead", type=int, default=3, help="segmentos siguientes como contexto (default: 3)")
    p.add_argument("--instructions", default="", help="instrucciones extra (glosario, tono, etc.)")
    p.add_argument("--json-output", type=Path, default=None, help="JSON de salida (default: json/<nombre del CSV de salida>.json)")
    p.add_argument("--limit", type=int, default=0, help="traducir solo los primeros N segmentos (pruebas)")
    args = p.parse_args()

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("Falta OPENAI_API_KEY (defínela en el archivo .env o como variable de entorno).")

    target_col = "target"
    rows = read_rows(args.input, args.source_col)
    if args.limit:
        rows = rows[: args.limit]
    done = load_done(args.output, target_col)
    json_path = args.json_output or JSON_DIR / (args.output.stem + ".json")
    for r in rows:
        r["target"] = done.get(r["segment_no"], "")

    system = SYSTEM_PROMPT.replace("@@SOURCE@@", args.source_lang).replace("@@TARGET@@", args.target_lang)
    if args.instructions:
        system += f"\n## 8. Instrucciones adicionales\n\n{args.instructions}\n"

    pending = [i for i, r in enumerate(rows) if not r["target"] and r["source"].strip()]
    print(f"{len(rows)} segmentos, {len(done)} ya traducidos, {len(pending)} por traducir "
          f"(modelo {args.model}).")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    def save():
        with open(args.output, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["segment_no", args.source_col, target_col])
            for r in rows:
                w.writerow([r["segment_no"], r["source"], r["target"]])
        write_json(json_path, rows, args.input, args.target_lang)

    try:
        for start in range(0, len(pending), args.batch_size):
            idxs = pending[start : start + args.batch_size]
            batch = [rows[i] for i in idxs]
            # Contexto: los N segmentos traducidos inmediatamente anteriores al lote.
            prev = [r for r in rows[: idxs[0]] if r["target"]][-args.context :] if args.context else []
            nxt = rows[idxs[-1] + 1 : idxs[-1] + 1 + args.lookahead]
            translated = translate_batch(api_key, args.model, system, prev, batch, nxt)
            for r, t in zip(batch, translated):
                r["target"] = t
                for w in check_format(t):
                    print(f"  aviso segmento {r['segment_no']}: {w}", file=sys.stderr)
            save()  # guarda tras cada lote: si algo falla, se puede reanudar
            print(f"  {start + len(idxs)}/{len(pending)} traducidos")
    except (RuntimeError, urllib.error.URLError, KeyboardInterrupt) as e:
        save()
        sys.exit(f"Interrumpido: {e}\nProgreso guardado en {args.output}; vuelve a ejecutar para reanudar.")

    save()
    print(f"Listo: {args.output}")


if __name__ == "__main__":
    main()
