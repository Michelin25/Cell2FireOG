"""Run a simple 100x100 Cell2Fire test with a power line in the middle.

This script does four things:
1. Creates a synthetic 100x100 dataset from the Sub40x40 toy inputs.
2. Runs the Cell2Fire C++ core on that dataset.
3. Reports how often the middle power-line cells are burned and total losses.
4. Builds a burn-probability map figure and highlights the power-line column.

The script uses weather mode "rows" by default for stability on custom datasets.

Important:
- We do NOT call `python -m cell2fire.main` here.
- Calling `main.py` imports plotting/stat modules (cv2), which can fail on headless HPC nodes.
- This script calls the C++ executable directly, so it is better suited for HPC batch runs.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_TOY_FOLDER = REPO_ROOT / "data" / "Sub40x40"
GENERATED_DATA_FOLDER = REPO_ROOT / "data" / "PowerLine100x100"
OUTPUT_FOLDER = REPO_ROOT / "outputs" / "PowerLine100x100"
CORE_BINARY = REPO_ROOT / "cell2fire" / "Cell2FireC" / "Cell2Fire"
WEATHER_MODE = "rows"
NWEATHERS = 1
USE_PREDEFINED_IGNITIONS = False


def as_c2f_folder_arg(folder: Path) -> str:
    """Return folder path string with trailing separator for Cell2Fire C++ CLI."""
    folder_str = str(folder)
    if folder_str.endswith("/"):
        return folder_str
    return folder_str + "/"


def copy_common_input_files() -> None:
    """Copy required inputs from the Sub40x40 toy dataset."""
    GENERATED_DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        "fbp_lookup_table.csv",
        "Weather.csv",
    ]

    # Optional: copy fixed ignitions.
    # If this is enabled and sim_years=1, all simulations use the same ignition.
    if USE_PREDEFINED_IGNITIONS:
        files_to_copy.append("Ignitions.csv")

    for file_name in files_to_copy:
        src = BASE_TOY_FOLDER / file_name
        dst = GENERATED_DATA_FOLDER / file_name
        shutil.copy2(src, dst)


def build_forest_asc(nrows: int = 100, ncols: int = 100) -> None:
    """Create a flat forest grid with one fuel type (C1 => grid value 1)."""
    forest_path = GENERATED_DATA_FOLDER / "Forest.asc"

    with forest_path.open("w", encoding="utf-8") as out:
        out.write(f"ncols {ncols}\n")
        out.write(f"nrows {nrows}\n")
        out.write("xllcorner 0\n")
        out.write("yllcorner 0\n")
        out.write("cellsize 100\n")
        out.write("NODATA_value -9999\n")

        row_values = " ".join(["1"] * ncols)
        for _ in range(nrows):
            out.write(row_values + "\n")


def build_data_csv(nrows: int = 100, ncols: int = 100) -> None:
    """Create Data.csv with C1 and flat terrain for all cells."""
    data_path = GENERATED_DATA_FOLDER / "Data.csv"

    header = [
        "fueltype",
        "mon",
        "jd",
        "M",
        "jd_min",
        "lat",
        "lon",
        "elev",
        "ffmc",
        "ws",
        "waz",
        "bui",
        "ps",
        "saz",
        "pc",
        "pdf",
        "gfl",
        "cur",
        "time",
        "pattern",
    ]

    total_cells = nrows * ncols

    with data_path.open("w", newline="", encoding="utf-8") as out:
        writer = csv.writer(out)
        writer.writerow(header)

        for _ in range(total_cells):
            # Simple, explicit values for a uniform/flat setup.
            row = [
                "C1", "", "", "", "", 51.0, -115.0, 0,
                "", "", "", "", 0, 0,
                "", "", 0.75, "", 20, "",
            ]
            writer.writerow(row)


def build_powerline_values(nrows: int = 100, ncols: int = 100) -> np.ndarray:
    """Create per-cell value map where the middle column is the power line.

    Normal cells = 1
    Power-line cells = 100
    """
    values = np.ones((nrows, ncols), dtype=np.float32)

    # For 100 columns, we use column 50 (1-based index) as the power line.
    powerline_col_index = (ncols // 2) - 1
    values[:, powerline_col_index] = 100.0

    values_path = GENERATED_DATA_FOLDER / "values100x100.csv"
    np.savetxt(values_path, values, fmt="%.1f", delimiter=" ")
    return values


def ensure_core_binary_exists() -> None:
    """Ensure the C++ Cell2Fire executable exists."""
    if CORE_BINARY.exists():
        return

    print("Cell2Fire core binary not found. Building it with make...")
    subprocess.run(["make", "-C", str(CORE_BINARY.parent)], check=True, cwd=REPO_ROOT)

    if not CORE_BINARY.exists():
        raise RuntimeError(f"Expected binary not found after build: {CORE_BINARY}")


def print_logfile_tail(logfile: Path, max_lines: int = 60) -> None:
    """Print the tail of the C++ logfile to make HPC errors easier to debug."""
    if not logfile.exists():
        print(f"Log file does not exist: {logfile}")
        return

    print("\n--- Tail of Cell2Fire log ---")
    lines = logfile.read_text(encoding="utf-8", errors="replace").splitlines()
    for line in lines[-max_lines:]:
        print(line)
    print("--- End of log tail ---\n")


def run_cell2fire_core(nsims: int = 20, sim_years: int = 1) -> None:
    """Run Cell2Fire C++ core directly (HPC-friendly path)."""
    if OUTPUT_FOLDER.exists():
        shutil.rmtree(OUTPUT_FOLDER)
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(CORE_BINARY),
        "--input-instance-folder", as_c2f_folder_arg(GENERATED_DATA_FOLDER),
        "--output-folder", as_c2f_folder_arg(OUTPUT_FOLDER),
        "--sim-years", str(sim_years),
        "--nsims", str(nsims),
        "--grids",
        "--final-grid",
        "--Fire-Period-Length", "1.0",
        "--output-messages",
        "--weather", WEATHER_MODE,
        "--nweathers", str(NWEATHERS),
        "--ROS-CV", "0.0",
        "--IgnitionRad", "0",
        "--seed", "123",
        "--ROS-Threshold", "0",
        "--HFI-Threshold", "0",
    ]

    if USE_PREDEFINED_IGNITIONS:
        cmd.append("--ignitions")

    logfile = OUTPUT_FOLDER / "LogFile.txt"
    try:
        with logfile.open("w", encoding="utf-8") as log:
            subprocess.run(cmd, check=True, cwd=REPO_ROOT, stdout=log, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError:
        print_logfile_tail(logfile)
        raise


def get_last_forest_grid_for_sim(sim_index: int) -> Path:
    """Find the final ForestGrid file for one simulation output folder."""
    sim_grid_folder = OUTPUT_FOLDER / "Grids" / f"Grids{sim_index}"
    forest_files = sorted(sim_grid_folder.glob("ForestGrid*.csv"))
    if not forest_files:
        raise RuntimeError(f"No ForestGrid files found in {sim_grid_folder}")
    return forest_files[-1]


def load_final_grids(nsims: int = 20) -> list[np.ndarray]:
    """Load final burn grids (0/1) for all simulations."""
    final_grids: list[np.ndarray] = []

    for sim in range(1, nsims + 1):
        grid_file = get_last_forest_grid_for_sim(sim)
        final_grid = np.loadtxt(grid_file, delimiter=",")
        final_grids.append(final_grid)

    return final_grids


def compute_burn_probability_map(final_grids: list[np.ndarray]) -> np.ndarray:
    """Compute burn probability at each cell from final simulation grids."""
    if len(final_grids) == 0:
        raise RuntimeError("No simulation grids were loaded to compute burn probability")

    grid_stack = np.stack(final_grids, axis=0)
    burn_probability_map = np.mean(grid_stack == 1, axis=0)

    # Helpful debug information: if all runs are identical, this list is often [0.0, 1.0].
    unique_values = np.unique(burn_probability_map)
    print(f"Unique burn-probability values in map: {unique_values[:10]}")

    return burn_probability_map


def plot_burn_probability_map(burn_prob: np.ndarray, output_png: Path) -> None:
    """Plot burn probability map and highlight the power-line column."""
    nrows, ncols = burn_prob.shape
    powerline_col_index = (ncols // 2) - 1

    plt.figure(figsize=(8, 7))
    image = plt.imshow(burn_prob, cmap="hot", vmin=0.0, vmax=1.0, origin="upper")
    plt.colorbar(image, label="Burn probability")

    # Draw vertical line through the center power-line column.
    plt.axvline(x=powerline_col_index, color="cyan", linestyle="--", linewidth=2, label="Power line")

    plt.title("Burn probability map (100x100)")
    plt.xlabel("Column index")
    plt.ylabel("Row index")
    plt.legend(loc="upper right")
    plt.tight_layout()
    plt.savefig(output_png, dpi=200)
    plt.close()

    print(f"Saved burn probability map: {output_png}")


def evaluate_losses(values: np.ndarray, final_grids: list[np.ndarray]) -> None:
    """Calculate hit frequency and loss on power-line cells."""
    nrows, ncols = values.shape
    powerline_col_index = (ncols // 2) - 1
    powerline_values = values[:, powerline_col_index]

    hit_count = 0
    losses = []

    for final_grid in final_grids:
        burned_powerline = final_grid[:, powerline_col_index] == 1
        loss_this_sim = float(np.sum(powerline_values[burned_powerline]))
        losses.append(loss_this_sim)

        if np.any(burned_powerline):
            hit_count += 1

    nsims = len(final_grids)
    hit_rate = hit_count / float(nsims)
    avg_loss = float(np.mean(losses))
    max_loss = float(np.max(losses))

    print("\n=== Power line test summary ===")
    print(f"Number of simulations: {nsims}")
    print(f"Power line cells per sim: {nrows}")
    print(f"Power line hit count: {hit_count}")
    print(f"Power line hit rate: {hit_rate:.2%}")
    print(f"Average power line loss: {avg_loss:.2f}")
    print(f"Maximum power line loss: {max_loss:.2f}")


def main() -> None:
    """Create dataset, run Cell2Fire core, summarize losses, and plot burn probability."""
    nrows = 100
    ncols = 100
    nsims = 20

    copy_common_input_files()
    build_forest_asc(nrows=nrows, ncols=ncols)
    build_data_csv(nrows=nrows, ncols=ncols)
    values = build_powerline_values(nrows=nrows, ncols=ncols)

    ensure_core_binary_exists()
    run_cell2fire_core(nsims=nsims, sim_years=1)

    final_grids = load_final_grids(nsims=nsims)
    evaluate_losses(values=values, final_grids=final_grids)

    burn_prob = compute_burn_probability_map(final_grids)
    plot_path = OUTPUT_FOLDER / "BurnProbabilityMap.png"
    plot_burn_probability_map(burn_prob=burn_prob, output_png=plot_path)


if __name__ == "__main__":
    main()
