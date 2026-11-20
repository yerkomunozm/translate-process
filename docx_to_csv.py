#!/usr/bin/env python3
"""Convierte el DOCX de traducción (tabla de segmentos XLIFF) a CSV.

Solo usa la librería estándar (el .docx es un zip con XML).

Uso:
    python3 docx_to_csv.py -i entrada.docx -o salida.csv
"""
import argparse
import csv
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


# Columnas de la tabla del docx, en orden.
# La col. "ID" viene como "<n° de segmento>\n<GUID>" y se separa en dos.
HEADER = ["segment_no", "id", "source_en", "target_es", "comment", "status"]


def text_of(el):
    """Texto de un elemento, respetando saltos de línea (<w:br>) y tabs."""
    parts = []
    for e in el.iter():
        if e.tag == W + "t":
            parts.append(e.text or "")
        elif e.tag == W + "br":
            parts.append("\n")
        elif e.tag == W + "tab":
            parts.append("\t")
    return "".join(parts)


def cell_text(tc):
    return "\n".join(text_of(p) for p in tc.findall(W + "p"))


def read_segments(docx_path):
    """Devuelve una lista de dicts, uno por segmento."""
    with zipfile.ZipFile(docx_path) as z:
        root = ET.fromstring(z.read("word/document.xml"))

    segments = []
    for tr in root.iter(W + "tr"):
        cells = [cell_text(tc) for tc in tr.findall(W + "tc")]
        # Se omiten la fila de título (1 celda) y la de encabezados ("ID", ...).
        if len(cells) != 5 or cells[0].strip() == "ID":
            continue
        raw_id, source, target, comment, status = cells
        seg_no, _, guid = raw_id.partition("\n")
        segments.append(
            {
                "segment_no": seg_no.strip(),
                "id": guid.strip(),
                "source_en": source,
                "target_es": target,
                "comment": comment,
                "status": status.strip(),
            }
        )
    return segments


# Columnas a eliminar del resultado.
DROP_COLUMNS = {"id", "comment", "status", "target_es"}  # solo se deja source_en

# Búsqueda y reemplazo (en orden), aplicado a todas las columnas de texto.
REPLACEMENTS = [
    ("{0]", ""),
    ("[0}", ""),
    ("[1]", " "),
]


def apply_filters(segments):
    """Aplica reemplazos de texto y elimina columnas."""
    result = []
    for seg in segments:
        row = {}
        for col, value in seg.items():
            if col in DROP_COLUMNS:
                continue
            for old, new in REPLACEMENTS:
                value = value.replace(old, new)
            # Colapsa espacios/tabs repetidos (los saltos de línea se conservan).
            value = re.sub(r"[ \t]{2,}", " ", value)
            row[col] = value
        result.append(row)
    return result


def write_csv(segments, out_path):
    header = [c for c in HEADER if c not in DROP_COLUMNS]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig para que Excel abra bien los acentos/ñ.
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=header)
        w.writeheader()
        w.writerows(segments)


def main():
    parser = argparse.ArgumentParser(description="Convierte un DOCX de segmentos XLIFF a CSV.")
    parser.add_argument("-i", "--input", required=True, type=Path, help="archivo .docx de entrada")
    parser.add_argument("-o", "--output", required=True, type=Path, help="archivo .csv de salida")
    args = parser.parse_args()
    src, dst = args.input, args.output
    segments = read_segments(src)
    filtered = apply_filters(segments)
    write_csv(filtered, dst)
    print(f"{len(segments)} segmentos leídos, {len(filtered)} escritos en {dst}")


if __name__ == "__main__":
    main()
