# Cell2Fire simulation inputs and tunable parameters

This note inventories what you can change when running Cell2Fire, based on the Python argument parser, the Python-to-C++ wrapper command construction, the C++ argument reader, and CSV/ASC readers.

## 1) Command-line parameters (Python entrypoint: `python cell2fire/main.py ...`)

Defined in `cell2fire/utils/ParseInputs.py`.

### Paths and run scope
- `--input-instance-folder` (`InFolder`, str, default `None`): folder with simulation inputs.
- `--output-folder` (`OutFolder`, str, default `None`): output folder.
- `--sim-years` (`sim_years`, int, default `1`): years per simulation.
- `--nsims` (`nsims`, int, default `1`): number of simulation replications.
- `--seed` (`seed`, int, default `123`): RNG seed.
- `--nweathers` (`nweathers`, int, default `1`): maximum weather index used in random-weather mode.
- `--nthreads` (`nthreads`, int, default `1`): Python-side argument (not currently forwarded by wrapper to C++ core).
- `--max-fire-periods` (`max_fire_periods`, int, default `1000`): hard cap on fire periods.
- `--IgnitionRad` (`IgRadius`, int, default `0`): neighborhood radius around ignition points.
- `--gridsStep` (`gridsStep`, int, default `60`): grid generation period step.
- `--gridsFreq` (`gridsFreq`, int, default `-1`): grid generation simulation frequency.

### Heuristic/treatment planning parameters
- `--heuristic` (`heuristic`, int, default `-1`): heuristic mode (`-1` disables heuristic flow).
- `--MessagesPath` (`messages_path`, str, default `None`): path to message files.
- `--GASelection` (`GASelection`, bool flag): use genetic algorithm selection.
- `--HarvestedCells` (`HCells`, str, default `None`): path to initial harvested cells CSV.
- `--msgheur` (`msgHeur`, str, default `""`): path to heuristic message files.
- `--applyPlan` (`planPath`, str, default `""`): path to treatment/harvesting plan.
- `--DFraction` (`TFraction`, float, default `1.0`): demand fraction.
- `--GPTree` (`GPTree`, bool flag): use global propagation tree.
- `--customValue` (`valueFile`, str, default `None`): custom objective/value file.
- `--noEvaluation` (`noEvaluation`, bool flag): generate plans without evaluation.

### Genetic algorithm hyperparameters
- `--ngen` (`ngen`, int, default `500`): generations.
- `--npop` (`npop`, int, default `100`): population size.
- `--tsize` (`tSize`, int, default `3`): tournament size.
- `--cxpb` (`cxpb`, float, default `0.8`): crossover probability.
- `--mutpb` (`mutpb`, float, default `0.2`): mutation probability.
- `--indpb` (`indpb`, float, default `0.5`): per-individual probability.

### Simulation behavior, outputs, and post-processing flags
- `--weather` (`WeatherOpt`, str, default `rows`): weather mode (`constant`, `random`, `rows`).
- `--spreadPlots`, `--finalGrid`, `--verbose`, `--ignitions`, `--grids`, `--simPlots`, `--allPlots`, `--combine`, `--no-output`, `--gen-data`, `--output-messages`, `--Prometheus-tuned`, `--trajectories`, `--stats`, `--correctedStats`, `--onlyProcessing`, `--bbo`, `--fdemand`, `--pdfOutputs`: boolean flags controlling simulation behavior and outputs.

### Core fire spread / intensity parameters
- `--Fire-Period-Length` (`input_PeriodLen`, float, default `60` min).
- `--Weather-Period-Length` (`weather_period_len`, float, default `60` min).
- `--ROS-Threshold` (`ROS_Threshold`, float, default `0.1` m/min).
- `--HFI-Threshold` (`HFI_Threshold`, float, default `0.1` kW/m in code help text typo says 10 default).
- `--ROS-CV` (`ROS_CV`, float, default `0.0`): stochastic ROS coefficient of variation.
- `--HFactor` (`HFactor`, float, default `1.0`): multiplier for head ROS.
- `--FFactor` (`FFactor`, float, default `1.0`): multiplier for flank ROS.
- `--BFactor` (`BFactor`, float, default `1.0`): multiplier for back ROS.
- `--EFactor` (`EFactor`, float, default `1.0`): ellipse adjustment factor.
- `--BurningLen` (`BurningLen`, float, default `-1.0`): burn duration in periods.

## 2) What actually reaches the C++ simulator from Python

The Python wrapper (`cell2fire/Cell2FireC_class.py`) forwards these options into the C++ binary call:

- `--input-instance-folder`, `--output-folder`
- `--ignitions`
- `--sim-years`, `--nsims`
- `--grids`, `--final-grid`
- `--Fire-Period-Length`
- `--output-messages`
- `--weather`, `--nweathers`
- `--ROS-CV`
- `--IgnitionRad`
- `--seed`
- `--ROS-Threshold`, `--HFI-Threshold`
- `--bbo`
- `--HarvestPlan` (populated from `--HarvestedCells` path)
- `--verbose`

Not currently forwarded in this wrapper despite being parsed in Python: `--HFactor`, `--FFactor`, `--BFactor`, `--EFactor`, `--Weather-Period-Length`, `--max-fire-periods`, `--nthreads`, many plotting/postprocessing flags (which are used in Python-side postprocess), and heuristic-only fields used by Python logic.

## 3) C++ CLI options accepted by the core binary

`cell2fire/Cell2FireC/ReadArgs.cpp` parses these options directly:

- Strings: `--input-instance-folder`, `--output-folder`, `--weather`, `--HarvestPlan`
- Boolean flags: `--output-messages`, `--trajectories`, `--no-output`, `--verbose`, `--ignitions`, `--grids`, `--final-grid`, `--PromTuned`, `--statistics`, `--bbo`
- Numeric: `--sim-years`, `--nsims`, `--Weather-Period-Length`, `--nweathers`, `--Fire-Period-Length`, `--IgnitionRad`, `--ROS-Threshold`, `--HFI-Threshold`, `--HFactor`, `--FFactor`, `--BFactor`, `--EFactor`, `--ROS-CV`, `--max-fire-periods`, `--seed`

## 4) Required/optional instance input files and their fields

The C++ constructor reads:

- `Forest.asc` (grid geometry and fuel raster)
- `Data.csv` (per-cell FBP inputs)
- `Weather.csv` (weather-by-period values)
- Optional `Ignitions.csv` (if `--ignitions`)
- Optional harvest plan CSV via `--HarvestPlan`
- Optional `BBOFuels.csv` (if `--bbo`)

### `Data.csv` fields (per cell)
Header expected (example in datasets):

`fueltype,mon,jd,M,jd_min,lat,lon,elev,ffmc,ws,waz,bui,ps,saz,pc,pdf,gfl,cur,time,pattern`

These are parsed into the FBP `inputs` struct values used by spread calculations.

### `Weather.csv` fields (per weather period)
Header expected:

`Scenario,datetime,APCP,TMP,RH,WS,WD,FFMC,DMC,DC,ISI,BUI,FWI`

This is where you control FFMC and other moisture/fire-weather drivers by period.

### `Ignitions.csv` fields
Typical header:

`Year,Ncell`

Each row fixes ignition cell per year (when `--ignitions` is enabled).

### `BBOFuels.csv` fields
Parsed as per-fuel factors (read when `--bbo` is active), used to tune spread/intensity behavior by fuel type.

## 5) Moisture-related parameters you can change

If you specifically want fuel-moisture controls:

- `ffmc` in `Data.csv` (cell baseline field, if used/populated).
- `FFMC`, `DMC`, `DC` columns in `Weather.csv` (time-varying moisture codes).
- `BUI` in both `Data.csv` and `Weather.csv` (build-up index).
- `RH`, `TMP`, and `APCP` in `Weather.csv` indirectly influence fire behavior and moisture context.
- `ROS-Threshold`, `HFI-Threshold`, `ROS-CV`, and ROS factor multipliers (`HFactor/FFactor/BFactor`) are direct simulation controls that modulate spread and continuation.

Note: foliar moisture content (FMC) is computed internally (`foliar_moisture(...)` in FBP code) rather than read as an explicit top-level CLI parameter.
