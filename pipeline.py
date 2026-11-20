#!/usr/bin/env python3
"""Orquesta el flujo completo: DOCX -> CSV (docx_to_csv.py) -> CSV traducido + JSON (translate_csv.py).

Uso:
    python3 pipeline.py -i input/episodio.docx
    python3 pipeline.py -i input/a.docx input/b.docx --limit 10
    python3 pipeline.py -i input/                      # todos los .docx de la carpeta

Salidas por cada DOCX (nombre base = nombre del DOCX sin extensión):
    output/<base>.csv      segmentos extraídos
    output/<base>_es.csv   traducción
    json/<base>_es.json    traducción en JSON

Cualquier opción que este script no reconozca se pasa tal cual a translate_csv.py
(--model, --batch-size, --target-lang, --instructions, --limit, ...).
"""
import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def run(script, *args):
    cmd = [sys.executable, str(HERE / script), *map(str, args)]
    print(f"$ {' '.join(cmd)}", flush=True)
    return subprocess.run(cmd).returncode


def collect_inputs(paths):
    docs = []
    for p in paths:
        if p.is_dir():
            docs += sorted(p.glob("*.docx"))
        elif p.suffix.lower() == ".docx" and p.exists():
            docs.append(p)
        else:
            sys.exit(f"No es un .docx ni una carpeta existente: {p}")
    if not docs:
        sys.exit("No se encontraron archivos .docx.")
    return docs


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-i", "--input", required=True, nargs="+", type=Path, help=".docx o carpeta(s) con .docx")
    ap.add_argument("--output-dir", type=Path, default=HERE / "output", help="carpeta de CSV (default: output/)")
    ap.add_argument("--json-dir", type=Path, default=HERE / "json", help="carpeta de JSON (default: json/)")
    ap.add_argument("--skip-extract", action="store_true", help="no regenerar el CSV si ya existe")
    args, translate_args = ap.parse_known_args()

    docs = collect_inputs(args.input)
    failed = []
    for n, doc in enumerate(docs, 1):
        base = doc.stem
        src_csv = args.output_dir / f"{base}.csv"
        out_csv = args.output_dir / f"{base}_es.csv"
        out_json = args.json_dir / f"{base}_es.json"
        print(f"\n[{n}/{len(docs)}] {doc.name}", flush=True)

        if args.skip_extract and src_csv.exists():
            print(f"  CSV ya existe, se omite la extracción: {src_csv}")
        elif run("docx_to_csv.py", "-i", doc, "-o", src_csv) != 0:
            failed.append((doc.name, "extracción"))
            continue

        if run("translate_csv.py", "-i", src_csv, "-o", out_csv, "--json-output", out_json, *translate_args) != 0:
            failed.append((doc.name, "traducción"))
            continue
        print(f"  OK: {out_csv}  |  {out_json}")

    print(f"\n{len(docs) - len(failed)}/{len(docs)} completados.")
    for name, stage in failed:
        print(f"  falló {stage}: {name}", file=sys.stderr)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
