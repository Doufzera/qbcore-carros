#!/usr/bin/env python3
"""Empacota um fabricante do pack PLOKMJNB para FiveM.
Preserva os binarios originais; NAO altera texturas, colisoes ou LODs.
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
from pathlib import Path

ALLOWED_STREAM = {
    ".yft", ".ytd", ".ydr", ".ybn", ".ycd", ".ymf", ".ymap", ".ytyp"
}
UNNEEDED = {".bak", ".log", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}
MAX_ZIP_BYTES = 1_800_000_000

def get_models(path: Path) -> list[str]:
    """Ler spawns exatos do XML; falhas interrompem apenas o carro."""
    root = ET.parse(path).getroot()
    models = []
    for node in root.iter():
        if node.tag.lower() == "modelname" and node.text and node.text.strip():
            models.append(node.text.strip().lower())
    return sorted(set(models))

def collect_registry(data_root: Path):
    owners = defaultdict(set)
    errors = []
    for meta in sorted(data_root.rglob("vehicles.meta")):
        rel = meta.relative_to(data_root).as_posix()
        try:
            for model in get_models(meta):
                owners[model].add(rel)
        except ET.ParseError as exc:
            errors.append((rel, str(exc)))
    canonical = {
        model: sorted(paths, key=lambda p: (p.casefold(), p))[0]
        for model, paths in owners.items()
    }
    duplicates = {name: sorted(paths) for name, paths in owners.items() if len(paths) > 1}
    return canonical, duplicates, errors

def data_kind(name: str) -> str | None:
    n = name.lower()
    if not n.endswith(".meta"):
        return None
    if n == "vehicles.meta":
        return "VEHICLE_METADATA_FILE"
    if n.startswith("handling") and n not in ("handling_original.meta", "handlingstock.meta"):
        return "HANDLING_FILE"
    if n.startswith("vehiclelayouts"):
        return "VEHICLE_LAYOUTS_FILE"
    if n.startswith("carcols"):
        return "CARCOLS_FILE"
    if n.startswith("carvariations"):
        return "VEHICLE_VARIATION_FILE"
    if "contentunlocks" in n:
        return "CONTENT_UNLOCKING_META_FILE"
    if n == "shop_vehicle.meta":
        return "VEHICLE_SHOP_DLC_FILE"
    return None

def create_manifest(files: list[Path], directory: Path) -> None:
    file_paths = [p.relative_to(directory).as_posix() for p in files]
    out = ["fx_version 'cerulean'", "game 'gta5'", "", "files {"]
    out.extend("    '" + p.replace("'", "\\'") + "'," for p in file_paths)
    out.extend(["}", ""])
    for p in files:
        kind = data_kind(p.name)
        if kind:
            rel = p.relative_to(directory).as_posix()
            out.append(f"data_file '{kind}' '{rel}'")
    out.append("")
    (directory / "fxmanifest.lua").write_text("\n".join(out), encoding="utf-8")

def write_csv(path: Path, columns: list[str], rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

def get_filename_collisions(source: Path):
    """Inspeciona indice do Git sem baixar o streaming das outras marcas."""
    repo = source.parent
    try:
        lines = subprocess.check_output(
            ["git", "-C", str(repo), "ls-tree", "-r", "--name-only",
             "HEAD", "PLOKS_CARS/stream"],
            text=True, timeout=90
        ).splitlines()
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return []
    grouped = defaultdict(list)
    for path in lines:
        if Path(path).suffix.lower() in ALLOWED_STREAM:
            grouped[Path(path).name.lower()].append(path)
    return [
        {"arquivo": key, "quantidade": len(paths), "origens": " | ".join(paths)}
        for key, paths in sorted(grouped.items())
        if len(paths) > 1
    ]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--brand", required=True)
    parser.add_argument("--output", default="dist", type=Path)
    args = parser.parse_args()

    brand = args.brand.strip().upper()
    if not re.fullmatch(r"[A-Z0-9_]{2,24}", brand):
        parser.error("Nome de fabricante invalido.")
    source = args.source.resolve()
    data_root = source / "data"
    data_brand = data_root / f"[{brand}]"
    stream_brand = source / "stream" / f"[{brand}]"
    if not data_brand.is_dir() or not stream_brand.is_dir():
        parser.error("Marca nao encontrada nas pastas data/ e stream/.")

    dest = args.output.resolve()
    if dest == source or source in dest.parents or dest == source.parent:
        parser.error("Saida nao pode ser interna ao repositorio de origem.")
    if dest.exists():
        parser.error("Diretorio de saida ja existe; use pasta nova.")
    dest.mkdir(parents=True)
    container = dest / "staging" / "[carros]"
    container.mkdir(parents=True)
    canonical, duplicates, errors = collect_registry(data_root)

    duplication_rows = [
        {"spawn": model, "selecionado": canonical[model],
         "outras_origens": " | ".join(p for p in paths if p != canonical[model])}
        for model, paths in sorted(duplicates.items())
    ]
    write_csv(dest / "DUPLICADOS_SPAWN.csv",
              ["spawn", "selecionado", "outras_origens"], duplication_rows)
    write_csv(dest / "CONFLITOS_ARQUIVOS_STREAM.csv",
              ["arquivo", "quantidade", "origens"], get_filename_collisions(source))

    rows = []
    packaged = 0
    total_bytes = 0
    items = sorted(data_brand.rglob("vehicles.meta"))
    for item in items:
        rel_folder = item.parent.relative_to(data_brand)
        origin_key = (Path(f"[{brand}]") / rel_folder / "vehicles.meta").as_posix()
        stream_dir = stream_brand / rel_folder
        row = {"pasta_origem": origin_key, "spawns": "", "situacao": "",
               "recurso": "", "bytes_stream": 0, "observacao": ""}
        try:
            models = get_models(item)
        except ET.ParseError as exc:
            row.update(situacao="IGNORADO", observacao=f"vehicles.meta XML invalido: {exc}")
            rows.append(row)
            continue
        row["spawns"] = ", ".join(models)
        if not models:
            row.update(situacao="IGNORADO", observacao="nenhum modelName localizado")
            rows.append(row)
            continue
        conflicting = [m for m in models if canonical.get(m) != origin_key]
        if conflicting:
            row.update(situacao="IGNORADO",
                       observacao="spawn repetido, selecionado outro arquivo: " +
                       ", ".join(conflicting))
            rows.append(row)
            continue
        if not stream_dir.is_dir():
            row.update(situacao="IGNORADO", observacao="sem pasta stream correspondente")
            rows.append(row)
            continue
        stream_files = [
            p for p in sorted(stream_dir.rglob("*"))
            if p.is_file() and p.suffix.lower() in ALLOWED_STREAM
        ]
        if not any(p.suffix.lower() == ".yft" for p in stream_files):
            row.update(situacao="IGNORADO", observacao="sem modelo .yft na pasta stream")
            rows.append(row)
            continue
        if not any(p.name.casefold() == f"{m}.yft".casefold()
                   for m in models for p in stream_files):
            row.update(situacao="IGNORADO",
                       observacao="modelo principal .yft nao corresponde ao modelName")
            rows.append(row)
            continue

        metas = [p for p in sorted(item.parent.rglob("*")) if p.is_file()
                 and p.suffix.lower() in (".meta", ".xml", ".dat", ".ytyp")
                 and p.name.lower() not in ("handling_original.meta", "handlingstock.meta")]
        invalid = []
        for meta in metas:
            if meta.suffix.lower() in (".meta", ".xml"):
                try:
                    ET.parse(meta)
                except ET.ParseError as exc:
                    invalid.append(f"{meta.name}: {exc}")
        if invalid:
            row.update(situacao="IGNORADO", observacao="XML de dados invalido: " +
                       " | ".join(invalid))
            rows.append(row)
            continue

        num = packaged + 1
        res_name = f"car_{brand.lower()}_{num:03d}"
        resource = container / res_name
        (resource / "data").mkdir(parents=True)
        (resource / "stream").mkdir()
        staged_meta = []
        for meta in metas:
            rel = meta.relative_to(item.parent)
            out = resource / "data" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(meta, out)
            staged_meta.append(out)
        for asset in stream_files:
            rel = asset.relative_to(stream_dir)
            out = resource / "stream" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset, out)
            total_bytes += asset.stat().st_size
        create_manifest(staged_meta, resource)
        row.update(situacao="INCLUIDO", recurso=res_name,
                   bytes_stream=sum(p.stat().st_size for p in stream_files),
                   observacao="original sem alteracoes de malha, LOD ou textura")
        rows.append(row)
        packaged += 1

    write_csv(dest / f"RELATORIO_{brand}.csv",
              ["pasta_origem", "spawns", "situacao", "recurso", "bytes_stream", "observacao"],
              rows)
    if errors:
        write_csv(dest / "XML_INVALIDOS_ORIGEM.csv", ["arquivo", "erro"],
                  [{"arquivo": p, "erro": err} for p, err in errors])
    if packaged == 0:
        sys.exit("ERRO: nenhum recurso valido gerado. Verifique os relatorios.")

    names_src = source / "vehicle_names.lua"
    if names_src.is_file():
        names = container / "car_ploks_nomes"
        names.mkdir()
        shutil.copy2(names_src, names / "vehicle_names.lua")
        (names / "fxmanifest.lua").write_text(
            "fx_version 'cerulean'\ngame 'gta5'\nclient_script 'vehicle_names.lua'\n",
            encoding="utf-8"
        )

    zip_path = dest / f"PLOKMJNB_{brand}_FIVEM.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=6, allowZip64=True) as archive:
        for file in sorted(container.rglob("*")):
            if file.is_file():
                archive.write(file, file.relative_to(dest / "staging").as_posix())
    with zipfile.ZipFile(zip_path, "r") as archive:
        broken = archive.testzip()
    if broken:
        sys.exit(f"ZIP corrompido em {broken}")
    if zip_path.stat().st_size >= MAX_ZIP_BYTES:
        sys.exit("ZIP excede o limite conservador de 1,8 GB; dividir esta marca.")

    included = sum(row["situacao"] == "INCLUIDO" for row in rows)
    summary = [
        f"Fabricante: {brand}",
        f"Recursos incluidos: {included}",
        f"Veiculos/pastas ignorados: {len(rows) - included}",
        f"Streaming original dos incluidos (bytes): {total_bytes}",
        f"ZIP (bytes): {zip_path.stat().st_size}",
        "Arquivos 3D e texturas nao foram reprocessados.",
        "NAO CERTIFICADO no FiveM/FXServer; teste em servidor de homologacao.",
        "Ao instalar marcas diferentes, mantenha car_ploks_nomes uma unica vez."
    ]
    (dest / f"RESUMO_{brand}.txt").write_text("\n".join(summary) + "\n", encoding="utf-8")
    print("\n".join(summary))

if __name__ == "__main__":
    main()
