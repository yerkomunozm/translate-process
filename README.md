# translate-process

Dos scripts en Python para preparar y traducir subtítulos:

1. [docx_to_csv.py](docx_to_csv.py): convierte un DOCX de traducción (tabla de segmentos XLIFF) a CSV, aplicando una serie de filtros.
2. [translate_csv.py](translate_csv.py): traduce ese CSV del inglés al español de Chile (es-CL) con la API de OpenAI.

## Requisitos

- Python 3.8+
- Sin dependencias externas (solo librería estándar).
- Para `translate_csv.py`: una API key de OpenAI en la variable de entorno `OPENAI_API_KEY`.

## Flujo

```
input/*.docx  ──docx_to_csv.py──▶  output/X.csv  ──translate_csv.py──▶  output/X_es.csv
```

---

## 1. docx_to_csv.py

```bash
python3 docx_to_csv.py -i <entrada.docx> -o <salida.csv>
```

Ejemplo:

```bash
python3 docx_to_csv.py \
  -i input/TheWire_S1E1_TH-en.srt.esCL.xliff_spa-CL.docx \
  -o output/TheWire_S1E1.csv
```

| Parámetro | Descripción |
|---|---|
| `-i`, `--input` | Archivo `.docx` de entrada (obligatorio) |
| `-o`, `--output` | Archivo `.csv` de salida (obligatorio). Las carpetas se crean si no existen |

### Formato del DOCX esperado

Una tabla de 5 columnas: `ID`, inglés, español, comentario y estado. La primera fila (título) y la de encabezados se omiten. La celda `ID` contiene el número de segmento y el GUID separados por un salto de línea.

El script lee las columnas con estos nombres internos:
`segment_no`, `id`, `source_en`, `target_es`, `comment`, `status`.

### Filtros aplicados

Se configuran en [docx_to_csv.py](docx_to_csv.py):

- **`DROP_COLUMNS`**: columnas que se eliminan del CSV. Actualmente `id`, `comment`, `status` y `target_es`, por lo que el CSV final solo tiene `segment_no` y `source_en`.
- **`REPLACEMENTS`**: búsqueda y reemplazo, en orden, sobre todas las columnas de texto:
  1. `{0]` → *(nada)*
  2. `[0}` → *(nada)*
  3. `[1]` → un espacio
- **Espacios**: después de los reemplazos, los espacios y tabs repetidos se colapsan a uno. Los saltos de línea se conservan.

Para modificar el resultado, edita esas constantes. Por ejemplo, quita `target_es` de `DROP_COLUMNS` para incluir la columna en español.

### Salida

CSV codificado en UTF-8 con BOM (`utf-8-sig`) para que Excel muestre bien tildes y ñ. Si prefieres UTF-8 simple, cambia la codificación en `write_csv`.

---

## 2. translate_csv.py

Toma el CSV (`segment_no`, `source_en`), envía los segmentos a un modelo de OpenAI y escribe un CSV con la traducción.

```bash
export OPENAI_API_KEY=sk-...
python3 translate_csv.py -i output/TheWire_S1E1.csv -o output/TheWire_S1E1_es.csv
```

Para probar con pocos segmentos antes de gastar en el archivo completo:

```bash
python3 translate_csv.py -i output/TheWire_S1E1.csv -o output/prueba.csv --limit 30
```

| Parámetro | Descripción |
|---|---|
| `-i`, `--input` | CSV de entrada (obligatorio) |
| `-o`, `--output` | CSV de salida (obligatorio) |
| `--source-col` | Columna a traducir (default: `source_en`) |
| `--model` | Modelo de OpenAI (default: `gpt-4o`) |
| `--batch-size` | Segmentos por llamada (default: 30) |
| `--context` | Segmentos previos ya traducidos que se envían como contexto (default: 5) |
| `--lookahead` | Textos en inglés de los segmentos siguientes que se envían como contexto (default: 3) |
| `--instructions` | Instrucciones extra que se agregan al prompt (glosario, tono, etc.) |
| `--limit` | Traduce solo los primeros N segmentos (pruebas) |

### Cómo funciona

- **Prompt**: el system prompt está en la constante `SYSTEM_PROMPT` del script. Define al modelo como traductor de subtítulos EN → es-CL, con reglas de fidelidad, variante chilena, formato de subtitulado (máx. 2 líneas de 42 caracteres, formato pirámide, diálogos con `- `) y manejo de etiquetas. Edítalo ahí para cambiar el comportamiento.
- **Respuesta estructurada**: se pide JSON con esquema estricto y se valida que vuelvan exactamente los mismos `id` del lote. Si no coinciden, se repite el lote hasta 3 veces.
- **Reintentos**: ante errores 429, 5xx o de red se reintenta con espera creciente.
- **Reanudación**: el CSV de salida se guarda después de cada lote. Si el proceso se interrumpe, al ejecutarlo de nuevo con el mismo `-o` se omiten los segmentos ya traducidos.
- **Avisos de formato**: si una traducción supera 2 líneas o 42 caracteres por línea, se imprime un aviso por stderr con el número de segmento. Solo informa, no corrige: ante un conflicto se prioriza la fidelidad al significado. El formato pirámide no se verifica automáticamente.
- **Sin dependencias**: llama a la API REST con `urllib`, no requiere instalar el SDK de `openai`.

### Salida

CSV en UTF-8 con BOM con las columnas `segment_no`, `source_en` y `target`. Los saltos de línea dentro de una traducción se conservan.

## Estructura

```
.
├── docx_to_csv.py     # DOCX → CSV
├── translate_csv.py   # CSV → CSV traducido (OpenAI)
├── input/             # DOCX de entrada
└── output/            # CSV generados
```
