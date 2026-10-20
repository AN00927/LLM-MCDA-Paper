"""Estimate seasonal window solar irradiance from TMY3 EPW weather data."""
from __future__ import annotations

import argparse
import json
import math
import os
import urllib.request
import zipfile
from pathlib import Path

import numpy as np

BASE_URL = ("https://climate.onebuilding.org/WMO_Region_4_North_and_Central_America/"
            "USA_United_States_of_America/PA_Pennsylvania/")
STATIONS = {
    "harrisburg": "USA_PA_Harrisburg.Intl.AP.723990_TMY3",
    "philadelphia": "USA_PA_Philadelphia.Intl.AP.724080_TMY3",
    "pittsburgh": "USA_PA_Pittsburgh.Intl.AP.725200_TMY3",
}
# Ground albedo: assumed. 0.2 is a common bare-ground value; no primary source found.
RHO_GROUND = 0.2
W_M2_PER_BTUH_FT2 = 3.15459
HEAT_RANGE_F = (5.0, 62.0)     # heat-mode scenario outdoor range (HVACScenarios.xlsx)
COOL_RANGE_F = (68.0, 102.0)   # AC-mode scenario outdoor range
WINDOWS = {
    "24h": list(range(1, 25)),
    "day8": list(range(9, 17)),
    "night8": [24, 1, 2, 3, 4, 5, 6, 7],
}
ORIENT = {"N": 0.0, "E": 90.0, "S": 180.0, "W": 270.0}
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def fetch_epw(name: str, epw_dir: Path) -> Path:
    epw = epw_dir / f"{name}.epw"
    if not epw.exists():
        epw_dir.mkdir(parents=True, exist_ok=True)
        zpath = epw_dir / f"{name}.zip"
        urllib.request.urlretrieve(BASE_URL + name + ".zip", zpath)
        with zipfile.ZipFile(zpath) as z:
            z.extract(f"{name}.epw", epw_dir)
    return epw


def read_epw(path: Path):
    lines = path.read_text(encoding="latin-1").splitlines()
    loc = lines[0].split(",")
    lat, lon, tz = float(loc[6]), float(loc[7]), float(loc[8])
    design = lines[1].split(",")
    # 2025 ASHRAE design conditions block (in each TMY3 EPW header). HSP p. 49 allows
    # TMY3 or ASHRAE 2009 99% values; the 2009 values are not in the file.
    # Heating fields after 'Heating': coldest month, 99.6% DB, 99% DB, ...
    i = design.index("Heating")
    heat_db99_c = float(design[i + 3])
    rows = [l.split(",") for l in lines[8:] if l.strip()]
    a = np.array([[float(r[1]), float(r[2]), float(r[3]), float(r[6]),
                   float(r[13]), float(r[14]), float(r[15])] for r in rows])
    assert a.shape[0] == 8760, a.shape
    return {"lat": lat, "lon": lon, "tz": tz, "heat_db99_f": heat_db99_c * 9 / 5 + 32,
            "month": a[:, 0].astype(int), "day": a[:, 1].astype(int),
            "hour": a[:, 2].astype(int), "tdb_f": a[:, 3] * 9 / 5 + 32,
            "ghi": a[:, 4], "dni": a[:, 5], "dhi": a[:, 6]}


def sun_position(d):
    """Solar altitude and azimuth (deg; azimuth clockwise from north) at mid-hour."""
    doy = np.array([sum(DAYS_IN_MONTH[:m - 1]) + dd for m, dd in zip(d["month"], d["day"])])
    # Spencer (1971), Search 2(5), p. 172. First EoT constant is 0.0000075 per the
    # erratum noted in pvlib (the original print shows 0.000075).
    g = 2 * math.pi * (doy - 1) / 365.0
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g)
            - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
            - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    eot_min = 229.18 * (0.0000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                        - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    lst = d["hour"] - 0.5
    solar_time = lst + (4.0 * (d["lon"] - 15.0 * d["tz"]) + eot_min) / 60.0
    omega = np.radians(15.0 * (solar_time - 12.0))
    phi = math.radians(d["lat"])
    sin_alt = np.sin(phi) * np.sin(decl) + np.cos(phi) * np.cos(decl) * np.cos(omega)
    alt = np.arcsin(np.clip(sin_alt, -1, 1))
    cos_az = (np.sin(decl) - np.sin(alt) * np.sin(phi)) / (np.cos(alt) * np.cos(phi))
    az = np.degrees(np.arccos(np.clip(cos_az, -1, 1)))
    az = np.where(omega > 0, 360.0 - az, az)          # afternoon: west of south
    return np.degrees(alt), az


def vertical_irradiance(d):
    alt, az = sun_position(d)
    up = alt > 0
    out = {}
    for k, psi in ORIENT.items():
        cos_inc = np.cos(np.radians(alt)) * np.cos(np.radians(az - psi))
        # Vertical tilt: sky-diffuse view factor (1 + cos 90)/2 = 0.5 and ground view
        # factor (1 - cos 90)/2 = 0.5 (isotropic model, as in pvlib; cf. D&B Eq. 2.15.1).
        beam = np.where(up, d["dni"] * np.clip(cos_inc, 0, None), 0.0)
        out[k] = beam + d["dhi"] * 0.5 + d["ghi"] * RHO_GROUND * 0.5
    out["avg4"] = (out["N"] + out["E"] + out["S"] + out["W"]) / 4.0
    return out


def hsp_seasons(d):
    """Building America HSP (2010) p. 49 heating/cooling months from TMY3 MAT."""
    mat = np.array([d["tdb_f"][d["month"] == m].mean() for m in range(1, 13)])
    heat = mat < 66.0
    cool = mat > 66.0
    if d["heat_db99_f"] <= 59.0:
        heat[[11, 0]] = True
    cool[[6, 7]] = True
    h0, c0 = heat.copy(), cool.copy()
    for m in range(12):
        n = (m + 1) % 12
        if not c0[m] and c0[n]:
            heat[n] = True
        if not h0[m] and h0[n]:
            cool[n] = True
    starts = [m for m in range(12) if c0[m] and not c0[(m - 1) % 12]]
    if not c0.all():
        for s in starts:
            cool[(s - 1) % 12] = True
    return mat, heat, cool


def monthly_window_means(I, d):
    return {w: np.array([I[(d["month"] == m) & np.isin(d["hour"], hrs)].mean()
                         for m in range(1, 13)]) for w, hrs in WINDOWS.items()}


def season_value(monthly, weights):
    w = np.asarray(weights, dtype=float)
    return float((monthly * w).sum() / w.sum())


def analyse(name, d):
    I = vertical_irradiance(d)
    mat, heat_m, cool_m = hsp_seasons(d)
    hours = np.array([DAYS_IN_MONTH[m - 1] for m in range(1, 13)], dtype=float)
    tdb = d["tdb_f"]
    in_heat = (tdb >= HEAT_RANGE_F[0]) & (tdb <= HEAT_RANGE_F[1])
    in_cool = (tdb >= COOL_RANGE_F[0]) & (tdb <= COOL_RANGE_F[1])
    bin_w_heat = np.array([(in_heat & (d["month"] == m)).sum() for m in range(1, 13)])
    bin_w_cool = np.array([(in_cool & (d["month"] == m)).sum() for m in range(1, 13)])
    res = {"station": name, "lat": d["lat"], "lon": d["lon"],
           "heat_db99_f": round(d["heat_db99_f"], 1),
           "MAT_F": [round(x, 1) for x in mat],
           "hsp_heating_months": [m + 1 for m in range(12) if heat_m[m]],
           "hsp_cooling_months": [m + 1 for m in range(12) if cool_m[m]],
           "bin_hours_heat_by_month": bin_w_heat.tolist(),
           "bin_hours_cool_by_month": bin_w_cool.tolist(),
           "monthly_W_m2": {}, "season_W_m2": {}}
    for orient in ("S", "E", "W", "N", "avg4"):
        mw = monthly_window_means(I[orient], d)
        res["monthly_W_m2"][orient] = {w: [round(x, 1) for x in v] for w, v in mw.items()}
        for w, v in mw.items():
            res["season_W_m2"][f"{orient}|{w}|HSP-heat"] = season_value(v, hours * heat_m)
            res["season_W_m2"][f"{orient}|{w}|HSP-cool"] = season_value(v, hours * cool_m)
            res["season_W_m2"][f"{orient}|{w}|BIN-heat"] = season_value(v, bin_w_heat)
            res["season_W_m2"][f"{orient}|{w}|BIN-cool"] = season_value(v, bin_w_cool)
            res["season_W_m2"][f"{orient}|{w}|annual"] = season_value(v, hours)
        res["season_W_m2"][f"{orient}|HOUR|heat"] = float(I[orient][in_heat].mean())
        res["season_W_m2"][f"{orient}|HOUR|cool"] = float(I[orient][in_cool].mean())
    # South-vertical daily totals (kWh/m2/day) for the NASA POWER cross-check.
    res["S_vertical_kwh_m2_day"] = [round(x * 24 / 1000, 3)
                                    for x in res["monthly_W_m2"]["S"]["24h"]]
    res["GHI_kwh_m2_day"] = [round(d["ghi"][d["month"] == m].mean() * 24 / 1000, 3)
                             for m in range(1, 13)]
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epw-dir", default="epw")
    ap.add_argument("--power", nargs="*", default=[])
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    power = dict(p.split("=", 1) for p in a.power)
    allres = {}
    for st, fname in STATIONS.items():
        d = read_epw(fetch_epw(fname, Path(a.epw_dir)))
        r = analyse(st, d)
        allres[st] = r
        print(f"\n=== {st} ({fname}) lat {r['lat']} lon {r['lon']}  99% heating DB "
              f"{r['heat_db99_f']} F")
        print("MAT F:", r["MAT_F"])
        print("HSP heating months:", r["hsp_heating_months"], " cooling months:",
              r["hsp_cooling_months"])
        print("in-range hours by month, heat:", r["bin_hours_heat_by_month"])
        print("in-range hours by month, cool:", r["bin_hours_cool_by_month"])
        print(f"{'orientation/window':<18}" + "".join(f"{s:>11}" for s in
              ("HSP-heat", "HSP-cool", "BIN-heat", "BIN-cool", "annual")))
        for orient in ("avg4", "S", "E", "W", "N"):
            for w in WINDOWS:
                vals = [r["season_W_m2"][f"{orient}|{w}|{s}"] for s in
                        ("HSP-heat", "HSP-cool", "BIN-heat", "BIN-cool", "annual")]
                print(f"{orient + ' ' + w:<18}" + "".join(f"{v:>11.1f}" for v in vals)
                      + "   W/m2")
        print(f"avg4 HOUR-bin diagnostic: heat {r['season_W_m2']['avg4|HOUR|heat']:.1f}, "
              f"cool {r['season_W_m2']['avg4|HOUR|cool']:.1f} W/m2")
        print("S vertical kWh/m2/day (TMY3, this model):", r["S_vertical_kwh_m2_day"])
        print("GHI kWh/m2/day (TMY3):", r["GHI_kwh_m2_day"])
        if st in power:
            # POWER climatology: SI_TILTED_AVG_VERTICAL is the equator-facing vertical,
            # ALLSKY_SFC_SW_DWN is GHI. Both in kW-hr/m^2/day.
            doc = json.load(open(power[st]))
            pj = doc["properties"]["parameter"]
            period = doc["header"]["range"]
            months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP",
                      "OCT", "NOV", "DEC"]
            pv = [pj["SI_TILTED_AVG_VERTICAL"][m] for m in months]
            pg = [pj["ALLSKY_SFC_SW_DWN"][m] for m in months]
            print(f"S vertical kWh/m2/day (NASA POWER, {period}):", pv)
            print(f"GHI kWh/m2/day (NASA POWER, {period}):", pg)
            print(f"annual S-vertical: TMY3 {np.mean(r['S_vertical_kwh_m2_day']):.3f} vs POWER "
                  f"{pj['SI_TILTED_AVG_VERTICAL']['ANN']:.3f}; GHI: TMY3 "
                  f"{np.mean(r['GHI_kwh_m2_day']):.3f} vs POWER {pj['ALLSKY_SFC_SW_DWN']['ANN']:.3f}")
            r["power_S_vertical"] = pv
            r["power_GHI"] = pg
    if a.json:
        with open(a.json, "w") as f:
            json.dump(allres, f, indent=1)
    return allres


if __name__ == "__main__":
    main()
