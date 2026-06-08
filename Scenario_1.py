from pathlib import Path
from astropy.io import fits
import shutil
import re

#калибровочные файлы
Calib_types = ("dark", "flat", "bias", "lamp")

#функция получения нужного заголовка файлы "fits"
def get_imagetype(fits_path: Path) -> str:
    try:
        with fits.open(fits_path) as hdul:
            val = str(hdul[0].header.get("IMAGETYP", "")).lower()
            print(f"[Header] {fits_path.name} -> IMAGETYP = '{val}'")
            return val
    except Exception as e:
        print(f"[Error] Failed to read {fits_path}: {e}")
        return ""

#функция определения типа файла "fits": calibration и science
def classify_file(fits_path: Path) -> str:
    imagetyp = get_imagetype(fits_path)

    for t in Calib_types:
        if t in imagetyp:
            print(f"[Classification] {fits_path.name} -> {t}")
            return t

    print(f"[Classification] {fits_path.name} -> science")
    return "science"

#функция перемещения не файлов "fits" в отдельную папку meta
def move_non_fits_to_meta(folder: Path):

    if not folder.exists():
        return

    meta_dir = folder / "meta"
    meta_dir.mkdir(exist_ok=True)

    # собираем список файлов
    files_to_move = []

    for item in folder.rglob("*"):

        if not item.is_file():
            continue

        # не трогаем FITS
        if item.suffix.lower() in [".fit", ".fits"]:
            continue

        # не трогаем уже существующею папку meta
        if "meta" in item.parts:
            continue

        files_to_move.append(item)

    # перемещаем
    for item in files_to_move:

        end_d = meta_dir / item.name

        try:

            # если файл уже существует
            if end_d.exists():

                stem = item.stem
                suffix = item.suffix

                counter = 1

                while end_d.exists():
                    end_d = meta_dir / f"{stem}_{counter}{suffix}"
                    counter += 1

            shutil.move(str(item), str(end_d))

            print(f" meta: {item} → {end_d}")
        except Exception as e:
            print(f" Ошибка создания папки meta: {e}")

#функция создания папок "science" и "calib"
def ensure_dirs(base: Path):
    print(f"[New folder] Creating folder: {base}")

    (base / "science").mkdir(exist_ok=True)
    calib = base / "calib"
    calib.mkdir(exist_ok=True)

    for t in Calib_types:
        (calib / t).mkdir(exist_ok=True)


# | Вторая часть |

# функция перемещения научных и калибровочных файлов в соотвествующие папки "science" и "calib"
def process_directory(Base_dir: Path):
    Base_dir = Path(Base_dir)

    print(f"[Scan] scan path: {Base_dir}")

    fits_found = [p for p in Base_dir.rglob("*") if p.suffix.lower() in (".fits", ".fit")]

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

    move_non_fits_to_meta(Base_dir)

#функции определения года и даты по папкам
def is_year_folder(name: str):
    return re.fullmatch(r"\d{4}", name) is not None

def is_date_folder(name: str):
    return len(name) == 10 and name[4] == "-" and name[7] == "-"

#функция создания папок сортировки в директории
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

        # определение года
         for year_dir in telescope_path.rglob("*"):

            if not year_dir.is_dir():
                continue

            if not is_year_folder(year_dir.name):
                continue

            year_name = year_dir.name

            print(f" Год: {year_name}")

            # определение даты
            for date_dir in year_dir.iterdir():

                if not date_dir.is_dir() or not is_date_folder(date_dir.name):
                    continue

                date_name = date_dir.name

                print(f" Папка даты: {date_name}")
            
                # Перемещение папок Calibration
            
                calib_src = date_dir / "calib"    
            
                if calib_src.exists():

                    calib_target = (calib_out /year_name / date_name)

                    calib_target.mkdir(parents=True, exist_ok=True)

                    for sub in ["flat", "bias", "dark", "lamp"]:

                        src = calib_src / sub

                        if src.exists():

                            end_d = calib_target / sub

                            if not end_d.exists():
                                shutil.move(str(src), str(end_d))
                                print(f" Перемещено: из {src} в {end_d}")
                            else:
                                print(f" Папка уже существует: {end_d}")


                # Перемещение папок Science

                science_src = date_dir / "science"

                if science_src.exists():

                    science_target = (science_out /year_name /date_name)

                    science_target.mkdir(parents=True, exist_ok=True)

                    end_d = science_target / "science"

                    if not end_d.exists():

                        shutil.move(str(science_src), str(end_d))
                
                #перемещение meta
                meta_target = (science_out /year_name /date_name /"meta")

                meta_target.mkdir(parents=True, exist_ok=True)

            # meta из calib
                calib_meta = date_dir / "meta"

                if calib_meta.exists():

                    for item in calib_meta.iterdir():

                        end_d = meta_target / item.name

                        if not end_d.exists():

                            shutil.move(str(item), str(end_d))
                            print(f" meta(calib): {item} → {end_d}")

                    # meta из science
                science_meta = date_dir / "meta"

                if science_meta.exists():

                    for item in science_meta.iterdir():

                        end_d = meta_target / item.name

                        if not end_d.exists():

                            shutil.move(str(item), str(end_d))
                            print(f" meta(science): {item} → {end_d}")

#Вставьте директорию папки с файлами для сортировки.
base = Path(r"___")
process_directory(base)

# корневая папка | нужно указывать папку "Observation" для переноса в новую директорию
Base_dir = Path(r"___")

for obs_dir in Base_dir.iterdir():

    if not obs_dir.is_dir():
        continue

    # observatory_id 
    for telescope_dir in obs_dir.iterdir():

        if telescope_dir.is_dir():
            process_telescope(telescope_dir)


