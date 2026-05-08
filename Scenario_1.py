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


def process_directory(base_dir: Path):
    base_dir = Path(base_dir)

    print(f"[Scan] scan path: {base_dir}")

    fits_found = [p for p in base_dir.rglob("*") if p.suffix.lower() in (".fits", ".fit")]

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




def is_date_folder(name: str):
    return len(name) == 10 and name[4] == "-" and name[7] == "-"


def process_telescope(telescope_path: Path):

    # создаём папку "observ_mode" в директории "...\Observation\observatory_id\instrument_id"
    # создаём папки calibration и science в папке observ_mode
    observ_mode_dir = telescope_path / "observ_mode"
    calib_out = observ_mode_dir / "calibration"
    science_out = observ_mode_dir / "science"

    calib_out.mkdir(parents=True, exist_ok=True)
    science_out.mkdir(parents=True, exist_ok=True)

    # поиск observation mode 
    for mode_dir in telescope_path.iterdir():

        if not mode_dir.is_dir() or mode_dir.name == "observ_mode":
            continue

        # ищем год
        for year_dir in mode_dir.iterdir():

            if not year_dir.is_dir():
                continue

            # ищем даты
            for date_dir in year_dir.iterdir():

                if not date_dir.is_dir() or not is_date_folder(date_dir.name):
                    continue

                date_name = date_dir.name
                year_name = year_dir.name

                print(f" Папка даты: {date_name}")

            
                # Перемещение папок Calibration
            

                calib_src = date_dir / "calib"

                if calib_src.exists():

                    calib_target = calib_out / year_name / date_name
                    calib_target.mkdir(parents=True, exist_ok=True)

                    for sub in ["flat", "bias", "dark", "lamp"]:

                        # src = source - папка из которой перемещают
                        src = calib_src / sub

                        if src.exists():

                            # end_d = end_directory - папка в которую перемещают
                            end_d = calib_target / sub

                            if not end_d.exists():
                                shutil.move(str(src), str(end_d))
                                print(f" Перемещено: из {src} в {end_d}")
                            else:
                                print(f" Папка уже существует: {end_d}")


                # Перемещение папок Science

                science_src = date_dir / "science"

                if science_src.exists():

                    science_target = science_out / year_name / date_name
                    science_target.mkdir(parents=True, exist_ok=True)

                    end_d = science_target / "science"

                    if not end_d.exists():
                        shutil.move(str(science_src), str(end_d))
                        print(f" Перемещено: из {src} в {end_d}")
                    else:
                        print(f" Папка уже существует: {end_d}")
            
base = Path(r"paste the directory to the folder with files")
process_directory(base)

# корневая папка | нужно указывать папку "Observation"
BASE_DIR = Path(r"paste the directory")

for obs_dir in BASE_DIR.iterdir():

    if not obs_dir.is_dir():
        continue

    # observatory_id 
    for telescope_dir in obs_dir.iterdir():

        if telescope_dir.is_dir():
            process_telescope(telescope_dir)


