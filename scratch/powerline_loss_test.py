"""Run a simple 100x100 Cell2Fire test with a power line in the middle.

This script does three things:
1. Creates a synthetic 100x100 dataset from the Sub40x40 toy inputs.
2. Runs Cell2Fire on that dataset.
3. Reports how often the middle power-line cells are burned and total losses.

The loss model uses Cell2Fire's native per-cell custom value input (--customValue).
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path
from typing import List

import numpy as np


# Keep paths explicit and simple.
REPO_ROOT = Path(__file__).resolve().parents[1]
BASE_TOY_FOLDER = REPO_ROOT / "data" / "Sub40x40"
GENERATED_DATA_FOLDER = REPO_ROOT / "data" / "PowerLine100x100"
OUTPUT_FOLDER = REPO_ROOT / "outputs" / "PowerLine100x100"


def copy_common_input_files() -> None:
    """Copy lookup table and weather from Sub40x40 toy data."""
    GENERATED_DATA_FOLDER.mkdir(parents=True, exist_ok=True)

    files_to_copy = [
        "fbp_lookup_table.csv",
        "Weather.csv",
    ]

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

        # Single vegetation type everywhere.
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
            # Very simple and explicit values:
            # - fueltype C1 everywhere
            # - elev, slope (ps), and aspect (saz) set to 0 for flat terrain
            row = [
                "C1", "", "", "", "", 51.0, -115.0, 0,
                "", "", "", "", 0, 0,
                "", "", 0.75, "", 20, "",
            ]
            writer.writerow(row)


def build_powerline_values(nrows: int = 100, ncols: int = 100) -> np.ndarray:
    """Create custom per-cell value map and save it as values100x100.csv.

    We treat the middle column as the power line. Normal cells have value 1.
    Power-line cells have value 100 to represent higher consequence loss.
    """
    values = np.ones((nrows, ncols), dtype=np.float32)

    # Middle column index for a 100-column grid is 49 (0-based), i.e., column 50 (1-based).
    powerline_col_index = (ncols // 2) - 1
    values[:, powerline_col_index] = 100.0

    values_path = GENERATED_DATA_FOLDER / "values100x100.csv"
    np.savetxt(values_path, values, fmt="%.1f", delimiter=" ")
    return values


def run_cell2fire(nsims: int = 20, sim_years: int = 1) -> None:
    """Run the simulator with the generated dataset."""
    if OUTPUT_FOLDER.exists():
        shutil.rmtree(OUTPUT_FOLDER)

    cmd: List[str] = [
        "python",
        "-m",
        "cell2fire.main",
        "--input-instance-folder",
        str(GENERATED_DATA_FOLDER),
        "--output-folder",
        str(OUTPUT_FOLDER),
        "--sim-years",
        str(sim_years),
        "--nsims",
        str(nsims),
        "--finalGrid",
        "--weather",
        "random",
        "--nweathers",
        "100",
        "--Fire-Period-Length",
        "1.0",
        "--ROS-CV",
        "0.0",
        "--seed",
        "123",
        "--IgnitionRad",
        "0",
        "--grids",
        "--output-messages",
        "--stats",
        "--ROS-Threshold",
        "0",
        "--HFI-Threshold",
        "0",
        "--customValue",
        str(GENERATED_DATA_FOLDER / "values100x100.csv"),
    ]

    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def get_last_forest_grid_for_sim(sim_index: int) -> Path:
    """Find the final ForestGrid file for one simulation output folder."""
    sim_grid_folder = OUTPUT_FOLDER / "Grids" / f"Grids{sim_index}"
    forest_files = sorted(sim_grid_folder.glob("ForestGrid*.csv"))
    if not forest_files:
        raise RuntimeError(f"No ForestGrid files found in {sim_grid_folder}")
    return forest_files[-1]


def evaluate_losses(values: np.ndarray, nsims: int = 20) -> None:
    """Calculate hit frequency and loss on the power-line cells."""
    nrows, ncols = values.shape
    powerline_col_index = (ncols // 2) - 1
    powerline_values = values[:, powerline_col_index]

    hit_count = 0
    losses = []

    for sim in range(1, nsims + 1):
        grid_file = get_last_forest_grid_for_sim(sim)
        final_grid = np.loadtxt(grid_file, delimiter=",")

        # Burned cells are encoded as 1 in final grid outputs.
        burned_powerline = final_grid[:, powerline_col_index] == 1
        loss_this_sim = float(np.sum(powerline_values[burned_powerline]))
        losses.append(loss_this_sim)

        if np.any(burned_powerline):
            hit_count += 1

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
    """Create dataset, run Cell2Fire, and report power line losses."""
    nrows = 100
    ncols = 100
    nsims = 20

    copy_common_input_files()
    build_forest_asc(nrows=nrows, ncols=ncols)
    build_data_csv(nrows=nrows, ncols=ncols)
    values = build_powerline_values(nrows=nrows, ncols=ncols)

    run_cell2fire(nsims=nsims, sim_years=1)
    evaluate_losses(values=values, nsims=nsims)


if __name__ == "__main__":
    main()
