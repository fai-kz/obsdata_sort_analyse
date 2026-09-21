from pathlib import Path
from collections import defaultdict
import logging
import re
import numpy as np
import astropy.units as u
from astropy.io import fits
from astropy.nddata import CCDData
from ccdproc import combine
import csv
from datetime import (datetime, timedelta)


LOG_FILE = Path(__file__).resolve().parent / "combinig_log.txt"

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8"), logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)


def get_temperature(file_path: Path):
   
    header = fits.getheader(file_path)

    value = header.get("CCD-TEMP")

    if value is None:
        value = header.get("TEMP")

    if value is None:
        return None

    try:
        return float(value)

    except (TypeError, ValueError):
        return None


def get_main_key(file_path: Path):
   
    header = fits.getheader(file_path)

    exposure = header.get("EXPOSURE")

    if exposure is None:
        return None

    bin_values = []

    for key in header.keys():

        key_upper = str(key).upper()

        if "BIN" in key_upper:

            bin_values.append((key_upper, str(header[key]).strip()))

    bin_values.sort()

    return (exposure, tuple(bin_values))


def temperature_groups(files):
    
    temperature_files = []

    for file_path in files:

        temperature = get_temperature(file_path)

        if temperature is None:

            logger.warning(f"Skipping {file_path.name}: " f"missing or invalid CCD-TEMP/TEMP")

            continue

        temperature_files.append((temperature, file_path))

    temperature_files.sort(key=lambda item: item[0])

    temp_groups = []

    current_group = []
    current_min_temp = None
    current_max_temp = None

    for temperature, file_path in temperature_files:

        if not current_group:

            current_group = [(temperature, file_path)]

            current_min_temp = temperature
            current_max_temp = temperature

            continue

        new_min_temp = min(current_min_temp, temperature)

        new_max_temp = max(current_max_temp, temperature)


        if new_max_temp - new_min_temp <= 2:

            current_group.append((temperature, file_path))

            current_min_temp = new_min_temp
            current_max_temp = new_max_temp

        else:

            temp_groups.append({"files": [item[1] for item in current_group], "min_temp": current_min_temp, "max_temp": current_max_temp})

            current_group = [(temperature, file_path)]

            current_min_temp = temperature
            current_max_temp = temperature

    if current_group:

        temp_groups.append({"files": [item[1] for item in current_group], "min_temp": current_min_temp, "max_temp": current_max_temp})

    return temp_groups


def create_master_calibration(calib_dir: Path, calibration_type: str = "dark", output_dir: Path | None = None, overwrite: bool = False):

    calib_dir = Path(calib_dir)

    logger.info("Starting calibration combining")
    logger.info(f"Calibration directory: {calib_dir}")
    logger.info(f"Calibration type: {calibration_type}")

#code is intended for dark calibration files
    if calibration_type.lower() != "dark":

        logger.error(f"Unsupported calibration file type: " f"{calibration_type}")

        return


    if output_dir is None:
        output_dir = (calib_dir.parent / "masters" / calibration_type)

    output_dir = Path(output_dir)



    fits_files = [
        p
        for p in calib_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() in (".fits", ".fit")
    ]

    logger.info(f"Found fits files: {len(fits_files)}")

    if not fits_files:

        logger.warning(f"Fits files not found: {calib_dir}")

        return


    groups = defaultdict(list)

    for file_path in fits_files:

        try:

            group_key = get_main_key(file_path)

        except Exception as e:

            logger.warning(f"Failed to read {file_path.name}: {e}")

            continue

        if group_key is None:

            logger.warning(f"Missing EXPOSURE: " f"{file_path.name}")

            continue

        groups[group_key].append(file_path)

    logger.info(f"Basic groups found: {len(groups)}")


    final_groups = []

    for group_key, files in groups.items():

        temp_groups = (temperature_groups(files))

        for temp_group in temp_groups:

            final_groups.append({"group_key": group_key, "files": temp_group["files"], "min_temp": temp_group["min_temp"], "max_temp": temp_group["max_temp"]})

    logger.info(f"Final combining groups: " f"{len(final_groups)}")

#creating combining groups

    for group_number, group in enumerate(final_groups, start=1):

        group_key = group["group_key"]
        files = group["files"]

        exposure = group_key[0]


        logger.info(f"EXPOSURE={exposure}," f"CCD-TEMP/TEMP=" f"files={len(files)}")

#requied at least two files
        if len(files) < 2:

            logger.warning("to merge require at least 2 files")

            continue

        ccd_list = []


        for file_path in files:

            try:

                ccd = CCDData.read(file_path, unit=u.adu)

                # Converting (1, 1024, 1024) to (1024, 1024)

                if ccd.data.ndim == 3:

                    ccd.data = np.squeeze(ccd.data)

                if ccd.data.ndim != 2:

                    logger.warning(f"Skipping {file_path.name}: " f"wrong size {ccd.data.shape}")

                    continue

                ccd_list.append(ccd)

            except Exception as e:

                logger.warning(f"Failed to read " f"{file_path.name}: {e}")

        if len(ccd_list) < 2:

            logger.warning("not enough valid files")

            continue

        reference_shape = (ccd_list[0].data.shape)

        if not all(ccd.data.shape == reference_shape for ccd in ccd_list):

            logger.warning("files are different sizes")

            continue

        logger.info("Creating master")
        
#combining calibration files
        try:

            master = combine(ccd_list, method="median", sigma_clip=True, sigma_clip_low_thresh=5, sigma_clip_high_thresh=5)

            master.header["IMAGETYP"] = "Master Dark"

            master.header.add_history("Average master dark")
            
        except Exception as e:

            logger.exception(f"Failed to combine group {e}")

            continue

        output_name = (f"master_{calibration_type}" f"_exp_{exposure}.fits")

        output_file = output_dir / output_name


#checking for existing master files
        if output_file.exists() and not overwrite:

            logger.debug(f"Master already exists, skipping: " f"{output_file}")

            continue


#output directory
        try:

            output_dir.mkdir(parents=True, exist_ok=True)

        except OSError as e:

            logger.error(f"Cannot create output directory " f"{output_dir}: {e}")

            continue


#writing master
        try:

            master.write(output_file, overwrite = overwrite)

            logger.info(f"master file created: {output_file}")

        except Exception as e:

            logger.exception(f"Failed to write " f"{output_file}: {e}")

    logger.info("Calibration combining finished")


def find_directories(base_dir: Path, mode: str, value: str | None = None):

    base_dir = Path(base_dir)
    logger.info(f"Mode: {mode}")
    logger.info(f"Value: {value}")

    if not base_dir.exists():

        logger.error(f"Directory does not exist: {base_dir}")

        return []

    if not base_dir.is_dir():

        logger.error(f"Path is not a directory: {base_dir}")

        return []

    dark_directories = []


#varaint All
    if mode == "all":

        search_dir = base_dir
        
        try:

           for directory in search_dir.rglob("*"):

               if not directory.is_dir():
                   continue

               if directory.name.lower() == "dark":

                   dark_directories.append(directory)

        except OSError as e:

           logger.error(f"Error while searching: {e}")

#variant Year

    elif mode == "year":

        for year in value:

            search_dir = base_dir / year

            if not search_dir.exists():

                logger.warning(f"Year directory does not exist: " f"{search_dir}")

                continue

            logger.info(f"Searching year: {year}")

            try:

                for directory in search_dir.rglob("*"):

                    if not directory.is_dir():
                        continue

                    if directory.name.lower() == "dark":
                        dark_directories.append(directory)

            except OSError as e:

                logger.error(f"Error searching {search_dir}: {e}")

#variant Date

    elif mode == "date":
        
        for date_string in value:

            year = date_string[:4]

            search_dir = (base_dir / year / date_string)

            if not search_dir.exists():

                logger.error(f"Date directory does not exist: " f"{search_dir}")

                continue

            try:

                for directory in search_dir.rglob("*"):

                    if not directory.is_dir():
                        continue

                    if directory.name.lower() == "dark":

                        dark_directories.append(directory)

            except OSError as e:

                logger.error(
                    f"Error searching " f"{search_dir}: {e}")

    else:

        logger.error(f"Unknown search mode: {mode}")

        return []

#search
    dark_directories = sorted(set(dark_directories))


    logger.info(f"Dark directories found: " f"{len(dark_directories)}")

    for dark_dir in dark_directories:

        logger.info(f"DARK: {dark_dir}")


    return dark_directories

def combining_mode():

    while True:

        command = input(
            "\nHow to combine dark calibration files?\n"
            "\n"
            "  All\n"
            "  Year YYYY\n"
            "  Date YYYY-MM-DD\n"
            "\n"
            "Enter command: "
        ).strip()

#option all

        if re.fullmatch(r"All", command, re.IGNORECASE):

            return "all", None

#option year to year


        match = re.fullmatch(r"Year\s+(\d{4})\s*-\s*(\d{4})", command, re.IGNORECASE)

        if match:
            start_year = int(match.group(1))
            end_year = int(match.group(2))

            if start_year > end_year:
                logging.warning("given years are equal")
                
                continue
            
            years = [str(year) for year in range(start_year, end_year + 1)]
            
            return "year", years
        
#option several years

        match = re.fullmatch(r"Year\s+((?:\d{4}\s*)+)", command, re.IGNORECASE)

        if match:

            years = re.findall(r"\d{4}", match.group(1))

            return "year", years


#option date to date

        match = re.fullmatch(r"Date\s+" r"(\d{4}-\d{2}-\d{2})" r"\s*-\s*" r"(\d{4}-\d{2}-\d{2})", command, re.IGNORECASE)

        if match:
            start_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()

            end_date = datetime.strptime(match.group(2), "%Y-%m-%d").date()

            if start_date > end_date:

                logging.warning("end_date must go after start_date")

                continue

            if start_date.year != end_date.year:

                logging.warining("date range must be in within the same year ")

                continue

            dates = []

            current_date = start_date

            while current_date <= end_date:

                dates.append(current_date.strftime("%Y-%m-%d"))

                current_date += timedelta(days=1)
                
            return "date", dates

#option several dates
        match = re.fullmatch(r"Date\s+" r"((?:\d{4}-\d{2}-\d{2}\s*)+)", command, re.IGNORECASE)

        if match:

            date_strings = re.findall(r"\d{4}-\d{2}-\d{2}", match.group(1))

           #checking each date correction

            valid_dates = []

            for date_string in date_strings:

                try:

                    datetime.strptime(date_string, "%Y-%m-%d")

                    valid_dates.append(date_string)

                except ValueError:

                    logging.warning("Incorect date")

                    break

            else:

                return "date", valid_dates

        
def get_overwrite_mode():

    while True:

        answer = input("\nOverwrite? y/n: ").strip().lower()

        if answer == "y":
            return True

        if answer == "n":
            return False

       
def find_master_files(base_dir):

    master_files = []

    for search_dir in base_dir:
        
        search_dir = Path(search_dir)

        if not search_dir.exists():
            continue

        try:
            for file_path in search_dir.rglob("*.fits"):

                if not file_path.is_file():
                    continue

                try:
                    header = fits.getheader(file_path, 0)

                    imagetyp = str(header.get("IMAGETYP", "")).strip().lower()

                    if imagetyp == "master dark".lower():
                        master_files.append(file_path)

                except Exception as e:
                    logger.warning(f"Failed to read header " f"{file_path}: {e}")

        except OSError as e:
            logger.error(f"Error while searching " f"{search_dir}: {e}")

    return sorted(set(master_files))

def get_binning_from_header(header):


    for key in header.keys():

        if "BIN" in str(key).upper():

            value = header[key]

            if value not in (None, "", " "):

                return value

    return ""

def get_ccd_temp_from_header(header):
    
    for key in header.keys():

        key_upper = str(key).upper()

        if key_upper == "CCD-TEMP":

            try:
                return float(header[key])
            except (TypeError, ValueError):
                return header[key]

    for key in header.keys():

        key_upper = str(key).upper()

        if key_upper == "TEMP":

            try:
                return float(header[key])
            except (TypeError, ValueError):
                return header[key]

    return ""

def get_image_size(header):

    width = header.get("NAXIS1", "")
    height = header.get("NAXIS2", "")

    return width, height



def update_csv(base_dir: Path, search_dirs, overwrite: bool):
    
#creating/updating data-base
    base_dir = Path(base_dir)

    csv_file = base_dir / "master_dark_database.csv"

    logger.info(f"csv database: {csv_file}")
    logger.info(f"Database search directories: {search_dirs}")

    master_files = find_master_files(search_dirs)

    if not master_files:

        logger.warning("No master FITS files found.")

        return

#reading csv
    existing_records = {}

    if csv_file.exists():

        try:

            with csv_file.open("r", newline="", encoding="utf-8-sig") as csv_input:

                reader = csv.DictReader(csv_input)

                for row in reader:

                    path = row.get("path", "")

                    exptime = row.get("exptime","")

                    binning = row.get("binning","")

                    record_key = (path, exptime, binning)

                    existing_records[record_key] = row

        except Exception as e:

            logger.exception(f"Failed to read csv database: {e}")

            return


#adding master files
    updated = 0
    added = 0
    skipped = 0

    for master_file in master_files:

        try:

            # getheader не требует fits.open()
            header = fits.getheader(master_file)

        except Exception as e:

            logger.warning(f"Failed to read header " f"{master_file}: {e}")

            continue


        date_obs = header.get("DATE-OBS",  "")
        
        if date_obs is not None:
            date_obs = header.get("DATE", "")
        else:
            date_obs = ""
        
        exptime = header.get("EXPOSURE","")


        binning = get_binning_from_header(header)

        
        width, height = get_image_size(header)

        ccd_temp = get_ccd_temp_from_header(header)


        path = str(master_file)


        record = {"path": path, "date_obs": date_obs, "exptime": exptime, "binning": binning, "width": width, "height": height, "ccd_temp": ccd_temp}

        record_key = (path, str(exptime), str(binning))

        if record_key in existing_records:

            if overwrite:

                existing_records[record_key] = record

                updated += 1

                logger.info(f"csv record updated: " f"{master_file}")

            else:

                skipped += 1

                logger.info(f"csv record unchanged: " f"{master_file}")


        else:

            existing_records[record_key] = record

            added += 1

            logger.info(f"csv record added: " f"{master_file}")


    fieldnames = ["path", "date_obs", "exptime", "binning", "width", "height", "ccd_temp"]

    try:

        records = list(existing_records.values())


        def sort_date(record):

            date_value = str(record.get("date_obs", "")).strip()

            if not date_value:
                return datetime.max

            try:
                return datetime.fromisoformat(date_value.replace("Z", ""))

            except ValueError:

#in case if format is not standard
                try:

                    return datetime.strptime(date_value[:10], "%Y-%m-%d")

                except ValueError:

#if no correct time writing - placed in the end
                    return datetime.max

        records.sort(key=sort_date)


        try:

            with csv_file.open("w", newline="", encoding="utf-8") as csv_output:

                writer = csv.DictWriter(csv_output, fieldnames=fieldnames)

                writer.writeheader()

                for record in records:

                    writer.writerow(record)

        except Exception as e:

            logger.exception(f"Failed to write scv database: {e}")

            return

    except Exception as e:

        logger.exception(f"Failed to write csv database: {e}")

        return



    logger.info(f"csv database updated: {csv_file}")

    logger.info(f"Added: {added}, " f"Updated: {updated}, "f"Skipped: {skipped}")

def database_updating_right(base_dir: Path, mode: str, value):
    
    base_dir = Path(base_dir)

#option all

    if mode == "all":
        return [base_dir]

#option year

    if mode == "year":
        search_dirs = []

        for year in value:
            year_dir = base_dir / year

            if year_dir.exists() and year_dir.is_dir():
                search_dirs.append(year_dir)

        return search_dirs

#option date

    if mode == "date":
        search_dirs = []

        for date_value in value:
            year = date_value[:4]

            date_dir = (
                base_dir
                / year
                / date_value
            )

            if date_dir.exists() and date_dir.is_dir():
                search_dirs.append(date_dir)

        return search_dirs

    return []

if __name__ == "__main__":

   
    directory_input = input("\nEnter directory with calibration files:\n").strip()

    directory_input = (directory_input.strip('"').strip("'"))

    base_dir = Path(directory_input)


    logger.info(f"Selected directory: {base_dir}")

    if not base_dir.exists():

        logger.error(f"Directory does not exist: {base_dir}")

    if not base_dir.is_dir():

        logger.error(f"Path is not a directory: {base_dir}")


    while True:

        overwrite_input = input("\nOverwrite? y/n: ").strip().lower()

        if overwrite_input == "y":

            overwrite = True
            break

        if overwrite_input == "n":

            overwrite = False
            break

    logger.info(f"Overwrite mode: {overwrite}")


    mode, value = combining_mode()

    logger.info(f"Search mode: {mode}, value: {value}")


    dark_directories = find_directories(base_dir=base_dir, mode=mode, value=value)


    if not dark_directories:
      
        logger.warning("No dark files directories found.")


    else:

        for number, dark_dir in enumerate(dark_directories, start=1):

            logger.info(f"{number}/{len(dark_directories)}: " f"{dark_dir}")

            try:

                create_master_calibration(calib_dir=dark_dir, calibration_type="dark", overwrite=overwrite)

            except Exception as e:

                logger.exception(f"ERROR processing " f"{dark_dir}: {e}")

            
#updating data-base
    database_search_dirs = database_updating_right(base_dir=base_dir, mode=mode, value=value)

    logger.info(f"Database search directories: " f"{database_search_dirs}"
)

    try:

        update_csv(base_dir=base_dir, search_dirs=database_search_dirs, overwrite=overwrite)

    except Exception as e:

        logger.exception(f"Failed to update master csv: {e}")
