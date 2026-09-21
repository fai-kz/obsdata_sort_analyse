from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from astropy.io import fits
from scipy.signal import find_peaks, peak_widths
from scipy.stats import pearsonr
import logging

def read_fits_data(fits_path):

    with fits.open(fits_path) as hdul:
        data = hdul[0].data

    if data is None:
        raise ValueError("No data in file")

    if data.ndim == 3:

        if data.shape[0] == 1:
            data = data[0]

        else:
            raise ValueError(f"unsupported size: {data.shape}")

    elif data.ndim != 2:

        raise ValueError(f"unsupported size: {data.shape}")

    return data

def calculate_row_intensity(fits_path):
    
    data = read_fits_data(fits_path)

    row_intensity = np.sum(data, axis=1)

    return row_intensity

def find_intensity_peaks(row_intensity):
    
    peaks, properties = find_peaks(row_intensity)

    if len(peaks) == 0:
        logging.warming("\nPeaks not found.")
        return np.array([], dtype=int)

    max_intensity = np.max(row_intensity)

    min_height = 0.11 * max_intensity
    max_height = 0.60 * max_intensity

    peak_values = row_intensity[peaks]

    height_mask = ((peak_values >= min_height) & (peak_values <= max_height))

    peaks = peaks[height_mask]

    logging.info("Pixel sum range:" "f{min_height:.2f} - {max_height:.2f")

    return peaks

def calculate_peak_widths(row_intensity, peaks):

    if len(peaks) == 0:
        return []

    widths, width_heights, left_ips, right_ips = peak_widths(row_intensity, peaks, rel_height=0.5)

    results = []

    for i in range(len(peaks)):

        peak_index = peaks[i]

        #peaks numeration
        peak_row = int(round(peak_index + 1))

        #boundaries
        left_row = int(round(left_ips[i] + 1))
        right_row = int(round(right_ips[i] + 1))

        # width in rows
        rounded_width = right_row - left_row

        results.append({
            "peak_row": peak_row,
            "peak_intensity": row_intensity[peak_index],

            "left_row": left_row,
            "right_row": right_row,

            "width": rounded_width,

            #for building a plot
            "width_height": width_heights[i],
            "left_ip": left_ips[i],
            "right_ip": right_ips[i]
        })

    return results

#full width half way of the peaks
def plot_row_intensity(fits_path, row_intensity, peaks, results):

    row_intensity = calculate_row_intensity(fits_path)

    row_numbers = np.arange(1, len(row_intensity) + 1)
    
    for i, result in enumerate(results, start=1):

        left_row = result["left_ip"] + 1
        right_row = result["right_ip"] + 1

        width_height = result["width_height"]

        plt.hlines(
        y=width_height,
        xmin=left_row,
        xmax=right_row,
        linewidth=2
    )

    #left boundary
        plt.scatter(
        left_row,
        width_height,
        marker="|",
        s=100,
        zorder=6
    )

    #right boundary
        plt.scatter(
        right_row,
        width_height,
        marker="|",
        s=100,
        zorder=6
    )

    #peak number
        plt.annotate(
        f"{i}",
        (
            result["peak_row"],
            result["peak_intensity"]
        ),
        xytext=(0, 8),
        textcoords="offset points",
        ha="center"
    )


#graphic building
    plt.figure(figsize=(12, 6))

    plt.plot(
        row_numbers,
        row_intensity,
        linewidth=1
    )

    plt.xlabel("row number")
    plt.ylabel("Total intensity")
    plt.title(
        f"Total intensity by row\n"
        f"{fits_path.name}"
    )

    plt.grid(True)

    plt.tight_layout()
    plt.show()



def print_peak_results(results):

    if not results:

        logging.warning("no appropiate peaks")

        return

    
def calculate_column_intensity(data, left_row, right_row):
#sum of intensity of the row in a specific range

    left_index = left_row - 1
    right_index = right_row


    selected_area = data[left_index:right_index,:]

   
    #sum the intensity along the height of the image.
    # axis=0 mean for each column, we sum the values ​​of all selected rows.


    column_intensity = np.sum(selected_area, axis=0)

    return column_intensity

def plot_multiple_column_intensity(profiles):

    plt.figure(
        figsize=(14, 7)
    )

    for profile in profiles:

        column_intensity = profile["column_intensity"]

        column_numbers = np.arange(1, len(column_intensity) + 1)

        plt.plot(
            column_numbers,
            column_intensity,
            linewidth=1.2,
            label=profile["file_name"]
        )

    plt.xlabel(
        "column number"
    )

    plt.ylabel(
        "Total intensity"
    )

    plt.title(
        "Column-wise intensity profiles\n"
    )

    plt.grid(True)


    plt.legend(
        title="file",
        loc="best"
    )

    plt.tight_layout()

    plt.show()
    
def process_multiple_files(file_paths):

    profiles = []

    for file_path in file_paths:

        try:

            data = read_fits_data(file_path)

          
            row_intensity = np.sum(data, axis=1)

           
            peaks = find_intensity_peaks(row_intensity)

           
            results = calculate_peak_widths(row_intensity, peaks)

            if not results:

                logging.warning("Peak width range not found.")

                continue

 
            first_peak = results[0]

            left_row = first_peak["left_row"]

            right_row = first_peak["right_row"]


            logging.info(f"rows: " f"{left_row} - {right_row}")

            logging.info(f"width: " f"{first_peak['width']} peaks.")


            column_intensity = calculate_column_intensity(data, left_row, right_row)


            profiles.append({
                "file_name": file_path.name,
                "file_path": file_path,
                "column_intensity": column_intensity,
                "left_row": left_row,
                "right_row": right_row
            })

        except Exception as exc:

            logging.error(f"Error during process " f"{file_path.name}:")

            print(exc)

    return profiles
    

def calculate_snr(signal):

    signal = np.asarray(signal, dtype=float)

    # deleting Nan & infinite
    signal = signal[np.isfinite(signal)]

    if len(signal) == 0:

        return np.nan

    mean_signal = np.mean(signal)

    std_signal = np.std(signal, ddof=0)

    if std_signal == 0:

        return np.inf

    snr_linear = (mean_signal / std_signal)

    snr_db = (20 * np.log10(abs(snr_linear)))

    return snr_db



def calculate_correlation(reference_signal, signal):

    reference_signal = np.asarray(reference_signal, dtype=float)

    signal = np.asarray(signal, dtype=float)

   
    if len(reference_signal) != len(signal):

        raise ValueError(
            "Profiles are different sizes: "
            f"{len(reference_signal)} "
            f"и "
            f"{len(signal)}."
        )


    valid = (np.isfinite(reference_signal) & np.isfinite(signal))

    reference_signal = (reference_signal[valid])

    signal = signal[valid]

    if len(reference_signal) < 2:

        raise ValueError("Not enough dots for correlation calculation")


    correlation, p_value = pearsonr(reference_signal, signal)

    return correlation, p_value

def find_reference_profile(profiles):

    valid_profiles = [profile for profile in profiles if np.isfinite(profile["snr"])]

    if not valid_profiles:

        raise ValueError("cannot undentify S/N for any file")

    reference = max(valid_profiles, key=lambda profile: profile["snr"])

    print(f"file: " f"{reference['file_name']}")

    print(f"S/N: " f"{reference['snr']:.3f} dB")

    return reference

def calculate_profiles_snr(profiles):

    for profile in profiles:

        signal = (profile["column_intensity"])

        snr = calculate_snr(signal)

        profile["snr"] = snr

        print(f"{profile['file_name']}: " f"S/N = {snr:.3f} dB")

    return profiles

def select_fits_files():

    directory = input(
        "\nEnter the path to the directory containing FITS files:\n> "
    ).strip()

    if not directory:
        logging.warning("\nDirectory not specified.")
        return []

    directory = Path(directory)

    if not directory.exists():
        logging.warning(
            f"\nDirectory not found:\n"
            f"{directory}"
        )
        return []

    if not directory.is_dir():
        logging.warning(
            f"\nThe specified path is not a directory.:\n"
            f"{directory}"
        )
        return []


    files_input = input(
        "\nEnter the names of the FITS files. "
        "separated by commas:\n> "
    ).strip()

    if not files_input:
        logging.warning("\nfiles not named")
        return []

    file_names = [
        name.strip()
        for name in files_input.split(",")
        if name.strip()
    ]

    file_paths = []

    for file_name in file_names:

        file_path = directory / file_name

        if not file_path.exists():

            logging.warning(
                f"\nfile is not found:\n"
                f"{file_path}"
            )

            continue

        if file_path.suffix.lower() not in [
            ".fits",
            ".fit"
        ]:

            logging.warning(
                f"\nThe file is not FITS:\n"
                f"{file_path.name}"
            )

            continue

        file_paths.append(file_path)

    return file_paths

def calculate_profiles_correlations(profiles, reference):

    reference_signal = (reference["column_intensity"])

    for profile in profiles:

        if profile is reference:

            profile["correlation"] = 1.0
            profile["p_value"] = 0.0

            print(f"{profile['file_name']}: " f"Correlation = 1.000000")

            continue

        signal = (profile["column_intensity"])

        try:

            correlation, p_value = (calculate_correlation(reference_signal, signal))

            profile["correlation"] = (correlation)

            profile["p_value"] = (p_value)

            print(
                f"{profile['file_name']}: "
                f"Correlation = "
                f"{correlation:.6f}, "
                f"p-value = "
                f"{p_value:.3e}"
            )

        except Exception as exc:

            print(
                f"{profile['file_name']}: "
                f"error of correlation"
            )

            print(exc)

            profile["correlation"] = np.nan
            profile["p_value"] = np.nan

    return profiles
    
if __name__ == "__main__":

    file_paths = select_fits_files()

    if not file_paths:

        logging.warning("\nNo file selected")

        return

    
    for file_path in file_paths:

        logging.info(f"  {file_path.name}")

    profiles = process_multiple_files(file_paths)

    if not profiles:

        logging.warning("\ncannot get any profile")

        return
    
    
    #для построения первого графика пиков по ширине снимка
    #plot_row_intensity(file_path, row_intensity, peaks, results )
   
    plot_multiple_column_intensity(profiles)

    profiles = calculate_profiles_snr(profiles)
    
    reference = find_reference_profile(profiles)

    # Корреляции
    profiles = calculate_profiles_correlations(profiles, reference)
    
    for profile in profiles:

        print(
            f"{profile['file_name']:<45} "
            f"S/N = {profile['snr']:>10.3f}   "
            f"Correlation = {profile['correlation']:>8.5f}"
        )
    

