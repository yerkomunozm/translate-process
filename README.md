# translate-process

Script en Python que convierte un DOCX de traducción (tabla de segmentos XLIFF) a CSV, aplicando una serie de filtros.

## Requisitos

- Python 3.8+
- Sin dependencias externas (solo librería estándar).

## Uso

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

## Formato del DOCX esperado

Una tabla de 5 columnas: `ID`, inglés, español, comentario y estado. La primera fila (título) y la de encabezados se omiten. La celda `ID` contiene el número de segmento y el GUID separados por un salto de línea.

El script lee las columnas con estos nombres internos:
`segment_no`, `id`, `source_en`, `target_es`, `comment`, `status`.

## Filtros aplicados

Se configuran en [docx_to_csv.py](docx_to_csv.py):

- **`DROP_COLUMNS`**: columnas que se eliminan del CSV. Actualmente `id`, `comment`, `status` y `target_es`, por lo que el CSV final solo tiene `segment_no` y `source_en`.
- **`REPLACEMENTS`**: búsqueda y reemplazo, en orden, sobre todas las columnas de texto:
  1. `{0]` → *(nada)*
  2. `[0}` → *(nada)*
  3. `[1]` → un espacio
- **Espacios**: después de los reemplazos, los espacios y tabs repetidos se colapsan a uno. Los saltos de línea se conservan.

Para modificar el resultado, edita esas constantes. Por ejemplo, quita `target_es` de `DROP_COLUMNS` para incluir la columna en español.

## Salida

CSV codificado en UTF-8 con BOM (`utf-8-sig`) para que Excel muestre bien tildes y ñ. Si prefieres UTF-8 simple, cambia la codificación en `write_csv`.

## Estructura

```
.
├── docx_to_csv.py   # script principal
├── input/           # DOCX de entrada
└── output/          # CSV generados
```
