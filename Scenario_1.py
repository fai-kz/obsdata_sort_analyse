from pathlib import Path
from uuid import uuid4
from astropy.io.fits import getheader
import shutil
import re
import logging
import os
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
from tqdm import tqdm

logging.basicConfig(level=logging.DEBUG, filename="sorting_log.log",filemode="w", format="%(asctime)s %(levelname)s %(message)s")

#калибровочные файлы
Calib_types = ("dark", "flat", "bias", "lamp")

#функция получения нужного заголовка файлы "fits"
def get_imagetype(fits_path: Path) -> str:
    try:
        header = getheader(fits_path)
        return str(header.get("IMAGETYP", "")).lower()
    except Exception as e:
        logging.debug(f"[Error] Failed to read {fits_path}: {e}")
        return ""

#функция определения типа файла "fits": calibration и science
def classify_file(fits_path: Path) -> str:
    imagetyp = get_imagetype(fits_path)
        
    for t in CALIB_TYPES:
        if t in imagetyp:
            #logging.debug(f"[Classification] {fits_path.name} -> {t}")
            return t

    return "science"

#функция перемещения не файлов "fits" в отдельную папку meta
def move_non_fits_to_meta(folder: Path):

    if not folder.exists():
        return

   try:
        end_d = meta_dir / folder.name
       
            # если файл уже существует
        if end_d.exists():

            end_d = (meta_dir / f"{folder.stem}_{uuid4().hex[:8]}{folder.suffix}")

        shutil.move(str(folder), str(end_d))

            #logging.info(f"meta: {item} -> {end_d}")

    except PermissionError:
            logging.warning(
                f"Файл заблокирован или нет прав доступа: {folder}"
            )

    except OSError as e:
            logging.warning(
                f"Ошибка доступа при перемещении {folder}: {e}"
            )

    except Exception as e:
            logging.error(
                f"Неожиданная ошибка при обработке {folder}: {e}"
            )

# | Вторая часть |

#Заранее вложение файлов в списки
def scan_files(root_dir):
    fits_files = []
    meta_files = []

    for dirpath, _, filenames in os.walk(root_dir):

        dirpath = Path(dirpath)

        for filename in filenames:

            file_path = dirpath / filename 
            
            if file_path.suffix.lower() in (".fits", ".fit"):
                fits_files.append(file_path)
                
            else:
                meta_files.append(file_path)
            
    return fits_files, meta_files

# функция перемещения научных и калибровочных файлов в соотвествующие папки "science" и "calib"
def process_directory(fits_path: Path):
   
    try:
        
        parent_dir = fits_path.parent
        
        file_type = classify_file(fits_path)

        if file_type == "science":
            target_dir = parent_dir / "science"
        else:
            target_dir = parent_dir / "calib" / file_type

        target_dir.mkdir(parents=True, exist_ok=True)
        
        target_path = target_dir / fits_path.name

        if target_path.exists():
            return
        
        shutil.move(str(fits_path), str(target_path))
        
    except Exception as e:
        print(f"[Error] moving error: {e}")

    #move_non_fits_to_meta(Base_dir)

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

            # определение даты
            for date_dir in year_dir.iterdir():

                if not date_dir.is_dir() or not is_date_folder(date_dir.name):
                    continue

                date_name = date_dir.name
            
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

                    for file in calib_meta.iterdir():

                        end_d = meta_target / file.name

                        if not end_d.exists():

                            shutil.move(str(file), str(end_d))
                        
                    # meta из science
                science_meta = date_dir / "meta"

                if science_meta.exists():

                    for file in science_meta.iterdir():

                        end_d = meta_target / file.name

                        if not end_d.exists():

                            shutil.move(str(file), str(end_d))

#|Запуск работы|
                          
if __name__ == "__main__":
    #Директория папки с файлами для сортировки
    base = Path(r"C:\Users\Nurken\Desktop\python\ML\Observation tzhao\tshao\zeiss1000_east\2025\2025-04-25")
    #process_directory(base)
    fits_files, meta_files = scan_files(base)

    #thread  = min(32, (os.cpu_count() or 1) * 4)

    with ProcessPoolExecutor(max_workers=8 ) as executor:

        futures = [
            executor.submit(process_directory, fits_path)
            for fits_path in fits_files
        ]

        for _ in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="FITS"
        ):
            pass
        
        
    meta_dir = base / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    with ProcessPoolExecutor(max_workers=8 ) as executor:

        futures = [
            executor.submit(
                move_non_fits_to_meta,
                meta_file,
                meta_dir
            )
            for meta_file in meta_files
        ]

        for _ in tqdm(
            as_completed(futures),
            total=len(futures),
            desc="META"
        ):
            pass

    # корневая папка | нужно указывать папку "Observation"
    base_dir = Path(r"C:\Users\Nurken\Desktop\python\ML\Observation tzhao")
    

    for obs_dir in base_dir.iterdir():

        if not obs_dir.is_dir():
            continue

        # observatory_id 
        for telescope_dir in obs_dir.iterdir():

            if telescope_dir.is_dir():
                process_telescope(telescope_dir)


