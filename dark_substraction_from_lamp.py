from pathlib import Path
import datetime
import csv
import logging
import os
from astropy.io.fits import getheader
from astropy import units as u
from astropy.nddata import CCDData
import ccdproc

LOG_FILE = Path(__file__).resolve().parent / "dark_substructing_log.txt"


logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.FileHandler("lamp_dark_subtraction.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def move_to_datetime(value):

    if value is None:
        return None

    value = str(value).strip()

    if not value:
        return None

    # ISO format
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass

    formats = [
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.datetime.strptime(value, fmt)
        except ValueError:
            continue

    return None


def get_header_value(header, keyword):
    
    keyword = keyword.upper()

    for key in header.keys():
        if str(key).upper() == keyword:
            return header[key]

    return None


def date_from_header(header):

    value = get_header_value(header, "DATE-OBS")

    if value is None:
        value = get_header_value(header, "DATE")

    return move_to_datetime(value)


def get_exposure(header):

    value = get_header_value(header, "EXPOSURE")

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_temperature(header):
    
    value = get_header_value(header, "CCD-TEMP")

    if value is None:
        value = get_header_value(header, "TEMP")    

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_bin_values(header):
   
    result = {}

    for key in header.keys():

        key_upper = str(key).upper()

        if "BIN" in key_upper:

            value = header[key]

            if value is None:
                value = ""

            result[key_upper] = str(value).strip()

    return result


def compare_bin_values(master_header, lamp_header):
 
    master_bin = get_bin_values(master_header)
    lamp_bin = get_bin_values(lamp_header)

    if set(master_bin.keys()) != set(lamp_bin.keys()):
        return False

    for key in master_bin:

        if master_bin[key] != lamp_bin[key]:
            return False

    return True


def find_date_directory(file_path):
    
    for parent in [file_path.parent, *file_path.parents]:

        try:
            datetime.datetime.strptime(parent.name, "%Y-%m-%d")

            return parent

        except ValueError:
            continue

    return None


def extract_object_name(file_path):
   #getting object name from lamp
   

    name = file_path.stem

    parts = name.split("_")

#sarching by name of file
    if parts[0].lower() == "lamp":

        if len(parts) >= 3:
            return parts[2]

        return None

    # object_1800_15s_1
    if parts:
        return parts[0]

    return None


def science_file_matches_object(science_file, object_name):

    if not object_name:
        return True

    return object_name.lower() in science_file.stem.lower()


def read_master_database(database_path):
    #database file information:
        #path
        #date_obs
        #exptime
        #binning
        #width
        #height
        #ccd_temp

    masters = []

    database_path = Path(database_path)

    if not database_path.exists():

        logging.warning(f"\ndatabase not found:" f"{database_path}")

        return masters

    with database_path.open("r", encoding="utf-8-sig", newline="") as file:

        reader = csv.DictReader(file)

        for row in reader:

            master_path = Path(row.get("path", "").strip())

            if not master_path.exists():

                logging.warning(f"\n master file not found:" f"{master_path}")

                continue

            master_date = move_to_datetime(row.get("date_obs"))

            if master_date is None:

                logging.warning(f"\n cannot get file's date" f":{master_path}")

                continue

            try:
                exposure = float(row.get("exptime", ""))
            except (TypeError, ValueError):
                exposure = None

            try:
                temperature = float(
                    row.get("ccd_temp", "")
                )
            except (TypeError, ValueError):
                temperature = None

            masters.append({
                "path": master_path,
                "date": master_date,
                "exposure": exposure,
                "temperature": temperature,
                "binning": row.get("binning","").strip()
            })

    return masters



def find_lamp_files(calibration_root):
  
    calibration_root = Path(calibration_root)

    lamp_files = []

#searching for lamp files    
    for file_path in calibration_root.rglob("*"):

        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in (".fits", ".fit"):
            continue

        if "lamp" not in file_path.name.lower():
            continue

        lamp_files.append(file_path)
    
    return lamp_files



def maching_lamp_with_master(master, lamp_path):
    #maching options:
    #1. DATE <= 90 days
     #2. EXPOSURE are same
      #3. TEMP/CCD-TEMP <= 2 C
       #4. BIN are same
    
    try:
        lamp_header = getheader(lamp_path, 0)

    except Exception as error:

        logging.error(f"cannot read header: " f"{lamp_path} | {error}")

        return None

    
    lamp_date = date_from_header(lamp_header)

    if lamp_date is None:
        return None

    date_difference = abs((master["date"] - lamp_date).days)

    if date_difference > 90:
        return None

#cheking exposure time

    lamp_exposure = get_exposure(lamp_header)

    master_exposure = master["exposure"]

    if (lamp_exposure is None or master_exposure is None):
        return None

    if lamp_exposure != master_exposure:
        return None

#temperature cheking
    lamp_temperature = get_temperature(lamp_header)

    master_temperature = master["temperature"]

    if (lamp_temperature is None or master_temperature is None):
        return None

    temperature_difference = abs(lamp_temperature - master_temperature)

    if temperature_difference > 2:
        return None

#Binning cheking
    try:
        master_header = getheader(master["path"], 0)

    except Exception as error:

        logging.error(f"cannot read master: " f"{master['path']} | {error}")

        return None

    if not compare_bin_values(master_header, lamp_header):
        return None


    return {
        "lamp_path": lamp_path,
        "lamp_date": lamp_date,
        "days": date_difference,
        "exposure": lamp_exposure,
        "temperature": lamp_temperature,
        "object": extract_object_name(lamp_path)
    }



#science object matching
def find_science_files(science_root, lamp_path, object_name):
    
    science_root = Path(science_root)

    lamp_date_dir = find_date_directory(lamp_path)

    if lamp_date_dir is None:
        return []

    date_name = lamp_date_dir.name

    try:
        date_value = datetime.datetime.strptime(date_name, "%Y-%m-%d")

    except ValueError:
        return []

    year = str(date_value.year)

    science_date_dir = (science_root / year / date_name)

    if not science_date_dir.is_dir():

        logging.warning(f"target-folder not found:" f"{science_date_dir}")

        return []

    science_files = []

    for file_path in science_date_dir.iterdir():

        if not file_path.is_file():
            continue

        if file_path.suffix.lower() not in (".fits", ".fit"):
            continue

        if "lamp" in file_path.name.lower():
            continue

        if file_path.name.lower().endswith("_dark"):
            continue

        if science_file_matches_object(file_path, object_name):
            science_files.append(file_path)

    return science_files


#master_dark
def subtract_dark_from_lamp(lamp_path, master_path):

    lamp_path = Path(lamp_path)
    master_path = Path(master_path)

    output_path = (lamp_path.parent / f"{lamp_path.name}")
    
    directory, filename = os.path.split(output_path)
    name, ext = os.path.splitext(filename)

    new_filename = f"{name}_dark{ext}"
    new_path = os.path.join(directory, new_filename)
    
    output_path = (lamp_path.parent / f"{new_path}")
    
    #if master file existed so don't rewrite it
    if output_path.exists():

        logging.debug(f"\nfile is exist:" f"\n{output_path}")

        return output_path

    try:

        lamp_file = CCDData.read(lamp_path, unit="adu")

        master_dark = CCDData.read(master_path, unit="adu")
        
        
        if lamp_file.data.ndim == 3 and lamp_file.data.shape[0] == 1:
            lamp_file.data = lamp_file.data[0]

        if master_dark.data.ndim == 3 and master_dark.data.shape[0] == 1:
            master_dark.data = master_dark.data[0]


#size comparing 
        if lamp_file.data.shape != master_dark.data.shape:

            raise ValueError(f"sizes of lamp & master dark not are same: " f"{lamp_file.data.shape} != " f"{master_dark.data.shape}")

        dark_subtracted = ccdproc.subtract_dark(
            lamp_file,
            master_dark,
            exposure_time="EXPOSURE",
            exposure_unit=u.second,
            scale=True
        )

        dark_subtracted.write(output_path, overwrite=False)
       
        return output_path

    except Exception as error:

        logging.exception(f"substraction error {error}")
        
        return None


def group_lamps_by_object(matches):
    
    groups = {}

    for item in matches:

        object_name = item["object"]

        if object_name not in groups:
            groups[object_name] = []

        groups[object_name].append(item)

    return groups


def process_masters(database_path, calibration_root, science_root):

    masters = read_master_database(database_path)

    if not masters:

        logging.warning("\n Database doesn't contain any master file")

        return

    lamp_files = find_lamp_files(calibration_root)

    if not lamp_files:

        logging.warning("\n No lamp files")

        return

    total_matches = 0
    total_processed = 0


    for master_number, master in enumerate(masters, start=1):

        matches = []

        for lamp_path in lamp_files:

            match = maching_lamp_with_master(master, lamp_path)

            if match is not None:

                match["master"] = master

                matches.append(match)

        if not matches:

            logging.warning("\n Appropriate lamp files not found")

            continue

        total_matches += len(matches)

        
        groups = group_lamps_by_object(matches)

        
        for object_name, object_lamps in groups.items():

            
            for item in object_lamps:

                lamp_path = item["lamp_path"]

               
                science_files = find_science_files(science_root, lamp_path, object_name)

                if science_files:
                    
                    for science_file in science_files:

                        logging.info(f"{science_file.name}")

                else:

                    logging.info("Target-file not found")

                
                result = subtract_dark_from_lamp(lamp_path, master["path"])

                if result is not None:
                    total_processed += 1


if __name__ == "__main__":

    base_dir = Path(
        input(
            "\nInsert direcory " "with Calibration and Target folders: ").strip().strip('"')
    )

    if not base_dir.is_dir():

        logging.warning("\nThis is not a directory")

        input("\n Enter for exit")
        raise SystemExit

    
    database_path = (base_dir / "master_dark_database.csv")

    calibration_root = (base_dir / "calibration")

    science_root = (base_dir / "targets")

    
    if not database_path.is_file():

        logging.warning("master_dark_database.csv not found")

        input(" Enter for exit")
        raise SystemExit

    if not calibration_root.is_dir():

        logging.warning("\n calibration folder not found")

        input("enter for exit")
        raise SystemExit

    if not science_root.is_dir():

        logging.warning("\nTarger folder not found")

        input("\nEnter for exit")
        raise SystemExit

    
    process_masters(database_path, calibration_root, science_root)


