"""Teste isolado: usa modelos ficticios, nunca baixa nem publica carros reais."""
import csv
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


def main():
    root = Path(tempfile.mkdtemp(prefix="ploks_test_"))
    src = root / "upstream" / "PLOKS_CARS"
    data = src / "data" / "[ACURA]"
    stream = src / "stream" / "[ACURA]"
    meta_body = (
        "<?xml version='1.0'?><CVehicleModelInfo__InitDataList>"
        "<InitDatas><Item><modelName>tltypes</modelName></Item>"
        "</InitDatas></CVehicleModelInfo__InitDataList>"
    )
    handling = (
        "<?xml version='1.0'?><CHandlingDataMgr>"
        "<HandlingData><Item><handlingName>tltypes</handlingName></Item>"
        "</HandlingData></CHandlingDataMgr>"
    )
    for folder in ["tltypes", "tltypes_copy"]:
        target = data / folder
        target.mkdir(parents=True)
        (target / "vehicles.meta").write_text(meta_body, encoding="utf-8")
        (target / "handling.meta").write_text(handling, encoding="utf-8")
        st = stream / folder
        st.mkdir(parents=True)
        (st / "tltypes.yft").write_bytes(b"RSC7TEST" * 32)
        (st / "tltypes_hi.yft").write_bytes(b"RSC7TEST" * 16)
        (st / "tltypes.ytd").write_bytes(b"RSC7TEXTURE")
        (st / "arquivo.bak").write_bytes(b"NO")

    (src / "vehicle_names.lua").write_text(
        "AddTextEntry('tltypes', 'Acura TL Type-S')\n", encoding="utf-8"
    )
    result = subprocess.run(
        [sys.executable, "tools/build_pack.py", "--source", str(src),
         "--brand", "ACURA", "--output", str(root / "dist")],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

    zip_path = root / "dist" / "PLOKMJNB_ACURA_FIVEM.zip"
    assert zip_path.is_file()
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        assert zf.testzip() is None
        assert "[carros]/car_acura_001/fxmanifest.lua" in names
        assert "[carros]/car_acura_001/data/vehicles.meta" in names
        assert "[carros]/car_acura_001/stream/tltypes.yft" in names
        assert "[carros]/car_ploks_nomes/vehicle_names.lua" in names
        assert not any(p.endswith(".bak") for p in names)
        assert not any("car_acura_002" in p for p in names)
        manifest = zf.read("[carros]/car_acura_001/fxmanifest.lua").decode()
        assert "VEHICLE_METADATA_FILE" in manifest
        assert "HANDLING_FILE" in manifest
    with (root / "dist" / "RELATORIO_ACURA.csv").open(
        encoding="utf-8-sig", newline=""
    ) as stream_csv:
        rows = list(csv.DictReader(stream_csv))
        assert len(rows) == 2, rows
        assert sorted(r["situacao"] for r in rows) == ["IGNORADO", "INCLUIDO"]
    with (root / "dist" / "DUPLICADOS_SPAWN.csv").open(
        encoding="utf-8-sig", newline=""
    ) as duplicates_csv:
        duplicates = list(csv.DictReader(duplicates_csv))
        assert len(duplicates) == 1 and duplicates[0]["spawn"] == "tltypes"
    print("PASSOU: ZIP, manifest, names, filtragem de .bak, duplicidade de spawns.")


if __name__ == "__main__":
    main()
