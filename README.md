# EXOTIC Standard — Local Edition

A standalone local version of NASA JPL's [EXOTIC Standard Colab notebook](https://colab.research.google.com/drive/1CNRbMQC0FmiVC9Pxj_lUhThgXqgbrVB_) for processing exoplanet transit observations from MicroObservatory robotic telescopes.

Instead of running in Google Colab with Google Drive, this script runs entirely on your own computer — Windows or Mac.

---

## What does this do?

This script takes FITS images from a MicroObservatory (or similar) telescope observation of an exoplanet transit and produces a light curve showing the planet passing in front of its host star. The output is an AAVSO-formatted data file you can submit to [Exoplanet Watch](https://exoplanets.nasa.gov/exoplanet-watch/).

The workflow:

1. **Load** your FITS images from a local folder
2. **Download** the exoplanet's orbital parameters from the NASA Exoplanet Archive
3. **Identify** the target star and comparison stars using an AAVSO star chart
4. **Run EXOTIC** to generate the transit light curve
5. **Submit** the output to AAVSO/Exoplanet Watch

---

## Step 1: Install Python

You need **Python 3.10** (EXOTIC does not yet support newer versions).

### Windows

1. Go to [python.org/downloads](https://www.python.org/downloads/release/python-31011/)
2. Download **Windows installer (64-bit)** for Python 3.10.x
3. Run the installer — **check the box "Add Python to PATH"** at the bottom of the first screen
4. Click "Install Now"
5. Verify it works — open **PowerShell** (search for "PowerShell" in the Start menu) and type:

```powershell
python --version
```

You should see `Python 3.10.x`.

### Mac

1. Go to [python.org/downloads](https://www.python.org/downloads/release/python-31011/)
2. Download **macOS 64-bit universal2 installer** for Python 3.10.x
3. Run the `.pkg` installer
4. Verify it works — open **Terminal** (search for "Terminal" in Spotlight) and type:

```bash
python3 --version
```

You should see `Python 3.10.x`.

> **Note for Mac users:** Use `python3` and `pip3` instead of `python` and `pip` throughout this guide. macOS ships with an older Python 2 as `python`, and the installer puts Python 3 at `python3`.

---

## Step 2: Install required packages

Open PowerShell (Windows) or Terminal (Mac) and run:

**Windows:**
```powershell
pip install exotic bokeh astropy matplotlib numpy Pillow requests ipython
```

**Mac:**
```bash
pip3 install exotic bokeh astropy matplotlib numpy Pillow requests ipython
```

This will take a few minutes. You only need to do this once.

---

## Step 3: Get your FITS images

If you're using MicroObservatory data:

1. Download your FITS images (`.fits` or `.fits.gz` files) from [MicroObservatory](https://waps.cfa.harvard.edu/microobservatory/MOImageDirectory/)
2. Put them all in one folder, e.g.:
   - Windows: `C:\Users\YourName\EXOTIC\Qatar-2b_20260328\`
   - Mac: `~/EXOTIC/Qatar-2b_20260328/`

Make sure the folder contains **only** the FITS files for a single observation session.

---

## Step 4: Download the script

Save `exotic_local.py` to a convenient location on your computer, for example:

- Windows: `C:\Users\YourName\EXOTIC\exotic_local.py`
- Mac: `~/EXOTIC/exotic_local.py`

---

## Step 5: Run the script

### Option A: Fully interactive (easiest)

Just run the script with no arguments. It will ask you for everything it needs.

**Windows (PowerShell):**
```powershell
cd C:\Users\YourName\EXOTIC
python exotic_local.py
```

**Mac (Terminal):**
```bash
cd ~/EXOTIC
python3 exotic_local.py
```

It will prompt you for:
- Path to your FITS images folder
- Exoplanet name (e.g. "Qatar-2 b")

### Option B: With arguments (faster for repeat runs)

You can pass everything on the command line to skip the prompts.

**Windows (PowerShell):**
```powershell
python exotic_local.py `
    --fits-dir "C:\Users\YourName\EXOTIC\Qatar-2b_20260328" `
    --planet "Qatar-2 b" `
    --aavso HANC `
    --no-clean
```

**Mac (Terminal):**
```bash
python3 exotic_local.py \
    --fits-dir ~/EXOTIC/Qatar-2b_20260328 \
    --planet "Qatar-2 b" \
    --aavso HANC \
    --no-clean
```

### Available arguments

| Argument | Description | Example |
|----------|-------------|---------|
| `--fits-dir` | Path to the folder with your FITS images | `"C:\EXOTIC\mydata"` |
| `--planet` | Exoplanet name (include the letter) | `"Qatar-2 b"` |
| `--star` | Host star name (usually auto-derived from planet name) | `"Qatar-2"` |
| `--telescope` | Telescope used | `MicroObservatory` (default) |
| `--aavso` | Your primary AAVSO observer code | `HANC` |
| `--aavso2` | Secondary AAVSO observer code (optional) | `SMIJ` |
| `--no-clean` | Skip the image review/cleaning step | |
| `--no-certificate` | Skip the participation certificate | |
| `--name` | Your name for the certificate | `"Jane Smith"` |

---

## Step 6: Identify your stars

After the script downloads the planetary parameters, it will open a window showing two images side by side:

- **Left:** Your telescope image (FITS) with pixel coordinates on the axes
- **Right:** The AAVSO star chart with the target star marked with crosshairs and comparison stars labeled with numbers

### Finding the target star
1. Look at the AAVSO chart (right) — the **crosshairs** in the center mark your target star
2. Find that same star in your telescope image (left)
3. Hover your mouse over it to read the pixel coordinates
4. Type the coordinates in `[x,y]` format, e.g. `[289,303]`

### Finding comparison stars
1. Look at the AAVSO chart for stars with **numbers** next to them — these are suggested comparison stars
2. Find at least 2 of those stars in your telescope image
3. Hover to read their coordinates
4. Type them in `[[x1,y1],[x2,y2]]` format, e.g. `[[422,227],[403,384]]`

### If the chart window closes or freezes

Type `star` at either coordinate prompt and press Enter — this will **reopen the chart window** so you can continue reading coordinates. You don't need to restart the script.

```
  Enter comp star coords [[x1,y1],[x2,y2],...]:  star
  Reopening chart window...
  Enter comp star coords [[x1,y1],[x2,y2],...]:  [[422,227],[403,384]]
```

---

## Step 7: Wait for EXOTIC to process

After you enter coordinates, EXOTIC will:

1. **Plate solve** your image (translate pixel coordinates to sky coordinates) — this takes 1-5 minutes
2. **Run photometry** on all your FITS images — this takes 5-30 minutes depending on how many images you have

You'll see a `Thinking - ...` spinner during the plate solve. This is normal — just let it run.

> **Important:** EXOTIC may ask if your pixel coordinates match its calculated coordinates. If it says they don't match and asks if you want to re-enter them, type `n` — it will then ask if you want to use its calculated coordinates instead. Type `y` to accept.

---

## Step 8: View your results

When EXOTIC finishes, it will display:

- **Light curve** — the transit dip showing the planet passing in front of the star
- **Field of view** — your image with the target and comparison stars marked
- **Triangle plot** — statistical analysis of the fit

All output files are saved in a folder next to your FITS folder with `_output` appended, e.g. `Qatar-2b_20260328_output/`.

---

## Step 9: Submit to AAVSO / Exoplanet Watch

1. Go to [app.aavso.org/exosite/submit](https://app.aavso.org/exosite/submit)
2. Upload the file named `AAVSO_<planet>_<date>.txt` from your output folder
3. Upload the light curve PNG image

> **Important:** If you get an error about `#OBSCODE=` being missing, open the AAVSO text file in a text editor, find the `#OBSCODE=` line near the top, and add your AAVSO observer code (e.g. `#OBSCODE=HANC`). This happens if you didn't pass `--aavso` when running the script.

---

## Troubleshooting

### "No module named 'exotic'" (or any other module)
You need to install the missing package:
```
pip install exotic
```
On Mac, use `pip3` instead of `pip`.

### "No module named 'IPython'"
```
pip install ipython
```

### The setuptools warning about "worked by accident"
This is harmless. To suppress it:
```
pip install --upgrade setuptools
```

### EXOTIC is stuck on "Thinking - ..."
This is the plate solver running — it can take several minutes. Wait at least 5-10 minutes before assuming it's stuck. If it truly hangs for more than 15 minutes, press Ctrl+C to cancel and try again.

### "Invalid \escape" JSON error
This is a Windows path issue. Make sure you're using the latest version of `exotic_local.py` — it includes a fix that converts Windows backslashes to forward slashes in the configuration file.

### Matplotlib window freezes when I click on it
Type `star` at the coordinate prompt to reopen a fresh chart window. This is a known issue with matplotlib's interactive mode on Windows.

### I entered the wrong coordinates
Delete the `inits.json` file from your output folder and re-run the script. It will prompt you for coordinates again.

---

## Getting your AAVSO Observer Code

If you don't have one yet:

1. Go to the [AAVSO New Observers page](https://www.aavso.org/new-observers)
2. Follow the instructions to request an observer code
3. Use your code with the `--aavso` argument when running the script

---

## Credits

- [EXOTIC](https://github.com/rzellem/EXOTIC) by NASA JPL / Exoplanet Watch
- [MicroObservatory](https://mo-www.cfa.harvard.edu/MicroObservatory/) by the Center for Astrophysics
- Original Colab notebook by the Exoplanet Watch team
- Local edition wrapper by the exoplanet observation community
