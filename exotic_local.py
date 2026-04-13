#!/usr/bin/env python3
"""
EXOTIC Standard — Local Edition
================================
A standalone local version of the EXOTIC Standard Google Colab notebook.
Processes MicroObservatory (or similar) FITS images of exoplanet transits
and generates light curves using NASA JPL's EXOTIC pipeline.

Works on both Windows and macOS with no extra configuration.

Original Colab notebook:
  https://colab.research.google.com/drive/1CNRbMQC0FmiVC9Pxj_lUhThgXqgbrVB_

Prerequisites:
  pip install exotic bokeh astropy matplotlib numpy Pillow requests ipython

Usage:
  python exotic_local.py --fits-dir ./my_fits_images --planet "Qatar-2 b"

  Or run interactively (no arguments) and follow the prompts.
"""

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import urllib.request
from pathlib import Path


# =====================================================================
# Helpers
# =====================================================================

# True when the user double-clicked the script (no CLI args).
# Used to decide whether to pause before exiting.
_INTERACTIVE_SESSION = False


def wait_and_exit(code=1):
    """Print a pause prompt so a double-click user can read the error,
    then exit.  In CLI mode (arguments provided) just exit immediately."""
    if _INTERACTIVE_SESSION:
        print()
        input("Press Enter to close this window...")
    sys.exit(code)


def check_dependencies():
    """Verify that the required packages are installed."""
    missing = []
    for pkg, import_name in [
        ("exotic", "exotic"),
        ("astropy", "astropy"),
        ("matplotlib", "matplotlib"),
        ("numpy", "numpy"),
        ("Pillow", "PIL"),
        ("bokeh", "bokeh"),
        ("requests", "requests"),
        ("ipython", "IPython"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("Missing packages — install with:")
        print(f"  pip install {' '.join(missing)}")
        wait_and_exit(1)


def find_fits_files(directory):
    """Return sorted list of FITS filenames in *directory*."""
    exts = (".fits", ".fits.gz", ".fit")
    return sorted(
        f for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and f.lower().endswith(exts)
    )


def find_inits_files(directory):
    """Return list of .json file paths in *directory*."""
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if os.path.isfile(os.path.join(directory, f))
        and f.lower().endswith(".json")
    )


def _find_system_font(bold=True):
    """Return a path to a usable TrueType font on this OS, or None."""
    candidates = []
    if platform.system() == "Windows":
        windir = os.environ.get("WINDIR", r"C:\Windows")
        if bold:
            candidates = [
                os.path.join(windir, "Fonts", "arialbd.ttf"),
                os.path.join(windir, "Fonts", "arial.ttf"),
                os.path.join(windir, "Fonts", "segoeui.ttf"),
            ]
        else:
            candidates = [
                os.path.join(windir, "Fonts", "arial.ttf"),
                os.path.join(windir, "Fonts", "segoeui.ttf"),
            ]
    elif platform.system() == "Darwin":  # macOS
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold
            else "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
            "/Library/Fonts/Arial.ttf",
        ]
    else:  # Linux
        candidates = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


# =====================================================================
# Step 1 — Validate inputs and discover files
# =====================================================================

def step1_load_images(fits_dir):
    """Locate FITS files and any existing inits.json."""
    fits_dir = os.path.abspath(fits_dir)
    if not os.path.isdir(fits_dir):
        print(f"ERROR: Directory not found: {fits_dir}")
        wait_and_exit(1)

    fits_files = find_fits_files(fits_dir)
    if not fits_files:
        print(f"ERROR: No .fits/.fit/.fits.gz files found in {fits_dir}")
        wait_and_exit(1)

    inits = find_inits_files(fits_dir)
    first_image = os.path.join(fits_dir, fits_files[0])

    output_dir = fits_dir + "_output"
    os.makedirs(output_dir, exist_ok=True)

    print(f"\n  Directory : {fits_dir}")
    print(f"  FITS files: {len(fits_files)}")
    print(f"  JSON files: {len(inits)}")
    print(f"  Output dir: {output_dir}\n")

    return fits_dir, fits_files, inits, first_image, output_dir


# =====================================================================
# Step 2 — Download planetary parameters from NASA Exoplanet Archive
# =====================================================================

def step2_planetary_params(planet_name):
    """Query the NASA Exoplanet Archive for planet parameters.
    If running interactively, allows the user to retry with a corrected name."""
    from exotic.exotic import NASAExoplanetArchive
    from exotic.api.colab import fix_planetary_params

    attempt = planet_name
    while True:
        try:
            targ = NASAExoplanetArchive(planet=attempt)
            resolved_name = targ.planet_info()[0]

            if not targ.resolve_name():
                raise ValueError(f"'{attempt}' not found")

            print(f"  Found: {resolved_name}")
            p_param_string = targ.planet_info(fancy=True)
            p_param_dict = json.loads(p_param_string)
            planetary_params = fix_planetary_params(p_param_dict)
            print(f"  Planetary parameters loaded.\n")
            return planetary_params, resolved_name, resolved_name

        except Exception as exc:
            print(f"\n  ERROR: Could not find '{attempt}' in the NASA Exoplanet Archive.")
            print(f"         ({type(exc).__name__}: {exc})")
            print("  Check spelling/spacing at https://exoplanetarchive.ipac.caltech.edu/")
            print("  Examples: HAT-P-36 b, WASP-39 b, Qatar-2 b")
            print("  Note: the trailing letter (b, c, d…) is required.\n")

            if _INTERACTIVE_SESSION:
                retry = input("  Enter a corrected planet name (or press Enter to quit): ").strip()
                retry = _sanitize_input(retry) if retry else ""
                if not retry:
                    wait_and_exit(1)
                print(f"  Retrying with: '{retry}'...")
                attempt = retry
            else:
                wait_and_exit(1)


# =====================================================================
# Step 2b — Optional: visually inspect & remove bad images
# =====================================================================

def step2b_clean_images(fits_dir, fits_files):
    """Display each FITS image and let the user remove bad ones."""
    from astropy.io import fits as afits
    from astropy.visualization import ImageNormalize, ZScaleInterval
    import matplotlib.pyplot as plt
    import numpy as np
    import shutil

    bad_dir = os.path.join(fits_dir, "Bad Images")
    os.makedirs(bad_dir, exist_ok=True)

    print(f"\n  Reviewing {len(fits_files)} images.  Close each window to continue.")
    print("  Type 'r' + Enter to REMOVE, or just Enter to KEEP.\n")

    kept, removed = 0, 0
    for i, fname in enumerate(fits_files):
        fpath = os.path.join(fits_dir, fname)
        if not os.path.exists(fpath):
            continue

        with afits.open(fpath) as hdul:
            data = hdul[0].data

        norm = ImageNormalize(data, interval=ZScaleInterval(),
                              vmin=np.nanpercentile(data, 5),
                              vmax=np.nanpercentile(data, 99))
        fig, ax = plt.subplots(figsize=(6, 6))
        ax.imshow(data, cmap="viridis", norm=norm, origin="lower")
        ax.set_title(f"[{i+1}/{len(fits_files)}]  {fname}")
        ax.axis("off")
        plt.tight_layout()
        plt.show(block=False)
        plt.pause(0.3)

        choice = input(f"  ({i+1}/{len(fits_files)}) Keep or Remove? [Enter=keep / r=remove]: ").strip().lower()
        plt.close(fig)

        if choice == "r":
            shutil.move(fpath, os.path.join(bad_dir, fname))
            removed += 1
            print(f"    Removed {fname}")
        else:
            kept += 1

    print(f"\n  Kept {kept}, removed {removed}.\n")
    return find_fits_files(fits_dir)


# =====================================================================
# Step 3 — Identify target & comparison stars
# =====================================================================

def _fix_inits_json(inits_path):
    """Post-process the inits.json to fix two issues:
    1. Normalise Windows backslashes to forward slashes (prevents
       invalid JSON escape sequences like \\M or \\d).
    2. Ensure calibration frame directories (darks, flats, biases) are
       explicitly set to null so EXOTIC skips them silently instead of
       prompting the user.
    """
    with open(inits_path, "r") as f:
        raw = f.read()

    # ── Fix backslashes ──
    fixed = raw.replace("\\\\", "%%DOUBLE%%")
    fixed = fixed.replace("\\", "/")
    fixed = fixed.replace("%%DOUBLE%%", "\\\\")

    # ── Ensure darks/flats/biases are null ──
    try:
        d = json.loads(fixed)
        ui = d.get("user_info", {})
        for key in ["Directory of Flats", "Directory of Darks", "Directory of Biases"]:
            if key in ui and ui[key] in ("", "null", None, "none", "None"):
                ui[key] = None
            elif key not in ui:
                ui[key] = None
        fixed = json.dumps(d, indent=4)
    except json.JSONDecodeError:
        pass  # if we can't parse, at least the backslash fix still applies

    with open(inits_path, "w") as f:
        f.write(fixed)


def get_star_chart_url(telescope, star_target):
    """Build AAVSO star chart URLs for a given telescope + target."""
    params = {
        "MicroObservatory":         {"fov": 56.44, "mag": 15, "res": 150},
        "Exoplanet Watch .4 Meter": {"fov": 38.42, "mag": 15, "res": 150},
    }
    p = params.get(telescope, params["MicroObservatory"])
    base = "https://app.aavso.org/vsp"
    qs = (f"?star={star_target}&scale=D&orientation=CCD&type=chart"
          f"&fov={p['fov']}&maglimit={p['mag']}&resolution={p['res']}"
          f"&north=down&east=left&lines=True")
    json_url = f"{base}/api/chart/{qs}&format=json"
    web_url  = f"{base}/{qs}"
    return json_url, web_url


def fetch_star_chart_image_url(json_url):
    """Retrieve the actual starchart PNG URL from the AAVSO JSON API."""
    with urllib.request.urlopen(json_url) as resp:
        data = json.load(resp)
    return data["image_uri"].split("?")[0]


def _chart_viewer(img_data, vmin, vmax, chart_data, stop_event):
    """Runs in a separate process with its own matplotlib event loop.
    Must be at module level so Windows multiprocessing can pickle it."""
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt

    ncols = 2 if chart_data is not None else 1
    fig, axes = plt.subplots(1, ncols, figsize=(7 * ncols, 7))
    if ncols == 1:
        axes = [axes]

    axes[0].imshow(img_data, cmap="viridis", vmin=vmin, vmax=vmax,
                    origin="lower")
    axes[0].set_title("Your telescope image (hover for coords)")

    if chart_data is not None:
        axes[1].imshow(chart_data)
        axes[1].set_title("AAVSO Star Chart")
        axes[1].axis("off")

    plt.tight_layout()
    plt.show(block=False)

    # Keep the window alive until the main process signals us to stop
    while not stop_event.is_set():
        try:
            plt.pause(0.2)
        except Exception:
            break
    plt.close("all")


def step3_identify_stars(first_image, telescope, star_name,
                         planetary_params, fits_dir, output_dir,
                         aavso_code, sec_code):
    """Show telescope image + AAVSO chart, prompt for target/comp coords,
    then create the inits.json file."""
    from exotic.api.colab import make_inits_file
    import multiprocessing

    # ── Fetch AAVSO star chart ──
    print(f"  Fetching AAVSO star chart for '{star_name}' ({telescope})...")
    json_url, web_url = get_star_chart_url(telescope, star_name)

    starchart_image_url = None
    try:
        starchart_image_url = fetch_star_chart_image_url(json_url)
        print(f"  Star chart: {starchart_image_url}")
    except Exception as exc:
        print(f"  WARNING: Could not auto-fetch chart ({exc})")
        print(f"  Try manually: {web_url}")
        starchart_image_url = input("  Paste the star chart image URL here (or Enter to skip): ").strip() or None

    # ── Prepare image data for the chart viewer ──
    from astropy.io import fits as afits
    import numpy as np

    with afits.open(first_image) as hdul:
        img_data = hdul[0].data.astype(float)

    vmin = float(np.nanpercentile(img_data, 5))
    vmax = float(np.nanpercentile(img_data, 99))

    chart_img_array = None
    if starchart_image_url:
        try:
            import requests
            from PIL import Image as PILImage
            from io import BytesIO
            resp = requests.get(starchart_image_url, timeout=15)
            chart_img_array = np.array(PILImage.open(BytesIO(resp.content)))
        except Exception as e:
            print(f"  Could not download chart: {e}")

    # ── Launch / manage the chart viewer ──
    stop_event = multiprocessing.Event()
    viewer_proc = None

    def show_charts():
        nonlocal viewer_proc, stop_event
        # Kill any existing viewer
        if viewer_proc is not None and viewer_proc.is_alive():
            stop_event.set()
            viewer_proc.join(timeout=3)
            if viewer_proc.is_alive():
                viewer_proc.terminate()
        stop_event = multiprocessing.Event()
        viewer_proc = multiprocessing.Process(
            target=_chart_viewer,
            args=(img_data, vmin, vmax, chart_img_array, stop_event),
            daemon=True
        )
        viewer_proc.start()

    print("\n  Displaying your FITS image and the AAVSO star chart.")
    print("  The chart window runs independently — click, zoom, pan freely.")
    print('  TIP: Type "star" at any prompt to reopen the chart window.\n')
    show_charts()

    # ── Prompt for target coords ──
    print("  Find the TARGET star (crosshairs on the chart) in your image.")
    while True:
        targ_coords = input("  Enter target star coords [x,y]:  ").strip()
        if targ_coords.lower() == "star":
            print("  Reopening chart window...")
            show_charts()
            continue
        if re.match(r"\[\d+, ?\d+\]$", targ_coords):
            break
        print("  Format must be [x,y], e.g. [424,286]  (or type 'star' to reopen charts)")

    # ── Prompt for comparison star coords ──
    print("\n  Now find 2+ COMPARISON stars (numbered on the chart).")
    while True:
        comp_coords = input("  Enter comp star coords [[x1,y1],[x2,y2],...]:  ").strip()
        if comp_coords.lower() == "star":
            print("  Reopening chart window...")
            show_charts()
            continue
        if re.match(r"\[(\[\d+, ?\d+\],? ?)+\]$", comp_coords):
            break
        print("  Format must be [[x1,y1],[x2,y2]], e.g. [[326,365],[416,343]]  (or type 'star' to reopen charts)")

    # ── Close the chart viewer ──
    stop_event.set()
    if viewer_proc is not None and viewer_proc.is_alive():
        viewer_proc.join(timeout=3)
        if viewer_proc.is_alive():
            viewer_proc.terminate()

    # ── Build inits.json ──
    print(f"\n  Target coords: {targ_coords}")
    print(f"  Comp coords:   {comp_coords}")
    print("  Creating inits.json...")

    safe_output_dir = os.path.join(output_dir, "")

    inits_path = make_inits_file(
        planetary_params, fits_dir, safe_output_dir, first_image,
        targ_coords, comp_coords, "",
        aavso_code, sec_code, False
    )

    _fix_inits_json(inits_path)

    print(f"  Saved: {inits_path}\n")
    return inits_path


# =====================================================================
# Step 4 — Run EXOTIC
# =====================================================================

def step4_run_exotic(inits_file_path):
    """Run the EXOTIC reduction pipeline and display results."""
    import matplotlib.pyplot as plt
    from PIL import Image as PILImage

    with open(inits_file_path, encoding="utf-8") as f:
        d = json.load(f)

    planet = d["planetary_parameters"]["Planet Name"]
    date_obs = d["user_info"]["Observation date"]
    output_dir = d["user_info"]["Directory to Save Plots"]
    os.makedirs(output_dir, exist_ok=True)

    cmd = f'exotic -red "{inits_file_path}" -ov'
    print(f"  Running: {cmd}\n")
    result = subprocess.run(cmd, shell=True)

    if result.returncode != 0:
        print(f"\n  ERROR: EXOTIC exited with code {result.returncode}")
        print(f"\n  This is usually caused by a temporary AAVSO API outage or")
        print(f"  a problem with the comparison star coordinates.")
        print(f"\n  You can re-run EXOTIC directly with:")
        print(f"    {cmd}")
        return output_dir, planet, date_obs, False

    # ── Show results ──
    lightcurve = os.path.join(output_dir, f"FinalLightCurve_{planet}_{date_obs}.png")
    fov        = os.path.join(output_dir, "temp", f"FOV_{planet}_{date_obs}_LinearStretch.png")
    triangle   = os.path.join(output_dir, "temp", f"Triangle_{planet}_{date_obs}.png")
    aavso_file = os.path.join(output_dir, f"AAVSO_{planet}_{date_obs}.txt")

    for label, path in [("Light curve", lightcurve), ("FOV", fov), ("Triangle", triangle)]:
        if os.path.isfile(path):
            img = PILImage.open(path)
            fig, ax = plt.subplots(figsize=(10, 6))
            ax.imshow(img)
            ax.set_title(label)
            ax.axis("off")
            plt.tight_layout()
            plt.show()
        else:
            print(f"  {label} not found at {path}")

    if os.path.isfile(aavso_file):
        print(f"\n  AAVSO submission file: {aavso_file}")
    else:
        print(f"\n  WARNING: AAVSO output file not found at {aavso_file}")

    print(f"\n  All outputs saved to: {output_dir}\n")
    return output_dir, planet, date_obs, True


# =====================================================================
# Step 5 (optional) — Participation certificate
# =====================================================================

def step5_certificate(output_dir, planet_name, observer_name=""):
    """Generate an Exoplanet Watch participation certificate."""
    from PIL import Image as PILImage, ImageDraw, ImageFont
    from datetime import datetime
    import requests
    from io import BytesIO

    if not observer_name:
        observer_name = input("  Enter your name for the certificate (or Enter to skip): ").strip()
    if not observer_name:
        print("  Skipping certificate.\n")
        return

    template_url = "https://drive.google.com/uc?id=1AA-53_0rkVNhAK8rTXEB_ip4kib2Bw6J"
    try:
        resp = requests.get(template_url, timeout=15)
        img = PILImage.open(BytesIO(resp.content))
    except Exception as e:
        print(f"  Could not download certificate template: {e}")
        return

    draw = ImageDraw.Draw(img)
    w, _ = img.size
    today_display = datetime.today().strftime("%B %d, %Y")
    today_numeric = datetime.today().strftime("%Y-%m-%d")

    def load_font(size):
        font_path = _find_system_font(bold=True)
        if font_path:
            try:
                return ImageFont.truetype(font_path, size)
            except IOError:
                pass
        return ImageFont.load_default()

    name_font  = load_font(32)
    other_font = load_font(24)

    def centered(text, font, y, x_offset=0):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        return ((w - tw) / 2 + x_offset, y)

    draw.text(centered(observer_name, name_font, 200), observer_name, font=name_font, fill="black")
    draw.text(centered(planet_name, other_font, 355, 175), planet_name, font=other_font, fill="black")
    draw.text(centered(today_display, other_font, 329, 75), today_display, font=other_font, fill="black")

    safe_name = re.sub(r"[^\w\-]", "-", observer_name)
    safe_planet = re.sub(r"[^\w\-]", "-", planet_name)
    filename = f"{safe_name}_{safe_planet}_{today_numeric}_certificate.png"
    out_path = os.path.join(output_dir, filename)
    img.save(out_path)
    print(f"  Certificate saved: {out_path}\n")


# =====================================================================
# Main — CLI entry point
# =====================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="EXOTIC Standard — Local Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:

  # Fully interactive
  python exotic_local.py

  # Windows PowerShell
  python exotic_local.py `
      --fits-dir "C:\\Users\\You\\EXOTIC\\mobs" `
      --planet "Qatar-2 b" `
      --aavso HANC --no-clean

  # macOS / Linux
  python exotic_local.py \\
      --fits-dir ./EXOTIC/mobs \\
      --planet "Qatar-2 b" \\
      --aavso HANC --no-clean
        """
    )
    parser.add_argument("--fits-dir", type=str, default=None,
                        help="Path to folder containing .FITS images")
    parser.add_argument("--planet", type=str, default=None,
                        help='Exoplanet name, e.g. "Qatar-2 b"')
    parser.add_argument("--star", type=str, default=None,
                        help='Host star name (auto-derived from planet name if omitted)')
    parser.add_argument("--telescope", type=str, default="MicroObservatory",
                        choices=["MicroObservatory", "Exoplanet Watch .4 Meter"],
                        help="Telescope used (default: MicroObservatory)")
    parser.add_argument("--aavso", type=str, default="",
                        help="Primary AAVSO observer code")
    parser.add_argument("--aavso2", type=str, default="",
                        help="Secondary AAVSO observer code")
    parser.add_argument("--no-clean", action="store_true",
                        help="Skip the image cleaning/review step")
    parser.add_argument("--no-certificate", action="store_true",
                        help="Skip certificate generation")
    parser.add_argument("--name", type=str, default="",
                        help="Your name (for the certificate)")
    return parser.parse_args()


def _sanitize_input(raw):
    """Strip surrounding quotes, whitespace, and normalise the value.
    Handles the common mistake of pasting paths/names with extra quotes,
    e.g.  "Qatar-2 b"  →  Qatar-2 b
    """
    s = raw.strip()
    # Remove matched outer quotes (single or double)
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    return s


def _prompt(label, example=None, allow_empty=False):
    """Prompt the user for input with sanitisation and retry on empty."""
    hint = f" (e.g. {example})" if example else ""
    while True:
        raw = input(f"{label}{hint}: ")
        value = _sanitize_input(raw)
        if value or allow_empty:
            return value
        print("  ERROR: Input cannot be empty. Please try again.")


def main():
    global _INTERACTIVE_SESSION
    args = parse_args()

    # Detect if the user launched interactively (double-click / no args)
    _INTERACTIVE_SESSION = (
        args.fits_dir is None
        and args.planet is None
        and args.star is None
        and not args.aavso
    )

    check_dependencies()

    print("=" * 60)
    print("  EXOTIC Standard — Local Edition")
    print("=" * 60)

    # ── Gather inputs (with sanitisation) ──
    fits_dir = args.fits_dir
    if not fits_dir:
        fits_dir = _prompt("\nPath to FITS images folder",
                           example=r"C:\Users\You\EXOTIC\fits")

    planet_name = args.planet
    if not planet_name:
        planet_name = _prompt("Exoplanet name", example="Qatar-2 b")

    aavso_code = args.aavso
    if not aavso_code and _INTERACTIVE_SESSION:
        aavso_code = _sanitize_input(
            input("AAVSO observer code (or Enter to skip): ")
        )

    sec_code = args.aavso2

    # ── Step 1: discover files ──
    print("\n-- Step 1: Load telescope images --")
    fits_dir, fits_files, inits, first_image, output_dir = step1_load_images(fits_dir)

    inits_file_path = None

    if len(inits) == 1:
        print(f"  Found existing inits.json: {inits[0]}")
        use_existing = input("  Use this file? [Y/n]: ").strip().lower()
        if use_existing != "n":
            inits_file_path = inits[0]
            with open(inits_file_path) as f:
                d = json.load(f)
            stored_dir = d["user_info"].get("Directory to Save Plots", "")
            if stored_dir != output_dir:
                print(f"  NOTE: inits.json points output to {stored_dir}")
                print(f"        Your local output dir is   {output_dir}")

    if inits_file_path is None:
        # ── Step 2: get planetary params ──
        print("\n-- Step 2: Download planetary parameters --")
        planetary_params, resolved_name, planet_name = step2_planetary_params(planet_name)

        # Derive star name from the (possibly corrected) planet name
        star_name = args.star
        if not star_name:
            star_name = re.sub(r"\s+[a-zA-Z]$", "", planet_name).strip()
        print(f"  Host star: {star_name}")

        # ── Step 3: star identification ──
        print(f"\n-- Step 3: Identify target & comparison stars --")
        print(f"  Planet: {planet_name}  |  Star: {star_name}")
        inits_file_path = step3_identify_stars(
            first_image, args.telescope, star_name,
            planetary_params, fits_dir, output_dir,
            aavso_code, sec_code,
        )

    # ── Step 4: run EXOTIC ──
    print("\n-- Step 4: Run EXOTIC --")
    output_dir, planet, date_obs, success = step4_run_exotic(inits_file_path)

    # ── Step 5: certificate ──
    if success and not args.no_certificate:
        print("\n-- Step 5: Participation certificate (optional) --")
        step5_certificate(output_dir, planet_name, args.name)

    print("=" * 60)
    print("  Done!  Check your results in:")
    print(f"    {output_dir}")
    print("=" * 60)

    if _INTERACTIVE_SESSION:
        print()
        input("Press Enter to close this window...")


if __name__ == "__main__":
    # Required on Windows for multiprocessing (chart viewer)
    import multiprocessing
    multiprocessing.freeze_support()
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Cancelled by user.")
        if _INTERACTIVE_SESSION:
            input("Press Enter to close this window...")
        sys.exit(0)
    except Exception as exc:
        print("\n" + "=" * 60)
        print("  UNEXPECTED ERROR — please report this to Andrei")
        print("=" * 60)
        print(f"\n  {type(exc).__name__}: {exc}\n")
        import traceback
        traceback.print_exc()
        if _INTERACTIVE_SESSION:
            print()
            input("Press Enter to close this window...")
        sys.exit(1)
