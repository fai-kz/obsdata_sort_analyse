from pathlib import Path
from astropy.io import fits
import shutil


CALIB_TYPES = ("dark", "flat", "bias", "lamp")


def get_imagetype(fits_path: Path) -> str:
    try:
        with fits.open(fits_path) as hdul:
            val = str(hdul[0].header.get("IMAGETYP", "")).lower()
            print(f"[Header] {fits_path.name} -> IMAGETYP = '{val}'")
            return val
    except Exception as e:
        print(f"[Error] Failed to read {fits_path}: {e}")
        return ""


def classify_file(fits_path: Path) -> str:
    imagetyp = get_imagetype(fits_path)

    for t in CALIB_TYPES:
        if t in imagetyp:
            print(f"[Classification] {fits_path.name} -> {t}")
            return t

    print(f"[Classification] {fits_path.name} -> science")
    return "science"


def ensure_dirs(base: Path):
    print(f"[New folder] Creating folder: {base}")

    (base / "science").mkdir(exist_ok=True)
    calib = base / "calib"
    calib.mkdir(exist_ok=True)

    for t in CALIB_TYPES:
        (calib / t).mkdir(exist_ok=True)


def process_assy_directory(base_dir: Path):
    base_dir = Path(base_dir)

    print(f"[Scan] scan path: {base_dir}")

    fits_found = [p for p in base_dir.rglob("*") if p.suffix.lower() in (".fits", ".fit", ".fts")]

    print(f"[Info] Found FITS files: {len(fits_found)}")

    if not fits_found:
        print("[Error] files not found")
        return

    for fits_path in fits_found:
        print(f"\n[Found] {fits_path}")

        parent_dir = fits_path.parent
        print(f"[Path] {parent_dir}")

        # проверка на уже отсортированные
        if parent_dir.name in ("science", "dark", "flat", "bias", "lamp"):
            print("[Skip] sorted")
            #continue

        ensure_dirs(parent_dir)

        file_type = classify_file(fits_path)

        if file_type == "science":
            target_dir = parent_dir / "science"
        else:
            target_dir = parent_dir / "calib" / file_type

        target_path = target_dir / fits_path.name

        print(f"[Moved to] {fits_path} -> {target_path}")

        try:
            shutil.move(str(fits_path), str(target_path))
            print("[Done] moved")
        except Exception as e:
            print(f"[Error] moving error: {e}")


base = Path(r"C:\Users\Nurken\Desktop\python\ML\Observation test\Assy\azt-20\Calibration\2021\2021-01-05")
process_assy_directory(base)


