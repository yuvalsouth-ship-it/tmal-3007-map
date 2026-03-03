"""
convert_shp.py
--------------
ממיר קבצי SHP של התכנית ל-GeoJSON ומשלב נתוני בעלות מ-CSV.
כל מה שצריך: Python + geopandas

התקנה (פעם אחת):
    pip install geopandas

שימוש:
    python convert_shp.py

בסיום ייווצר: data/parcels_merged.geojson  → ניתן לפתוח ישירות ב-index.html
"""

import sys
import os
import json

# ── ייבוא geopandas ──────────────────────────────────────────────────────────
try:
    import geopandas as gpd
    import pandas as pd
except ImportError:
    print("❌  חסר: geopandas")
    print("   הרץ: pip install geopandas")
    sys.exit(1)


# ===================================================================
#  ⚙️  הגדרות — שנה כאן לפי הצורך
# ===================================================================

# נתיב לקובץ SHP הראשי (ייעודי קרקע)
# אם ה-SHP בתת-תיקייה, שנה בהתאם, לדוגמה: "data/שם_תיקייה/parcels.shp"
SHP_PATH = "data/parcels.shp"

# נתיב לקובץ CSV עם נתוני בעלות
CSV_PATH = "data/ownership.csv"

# עמודה ב-SHP שמשמשת מספר תא שטח (מפתח חיבור)
SHP_PARCEL_KEY = "NAME"

# עמודה ב-CSV שמשמשת מספר תא שטח (מפתח חיבור)
CSV_PARCEL_KEY = "מספר תא שטח"

# שמות עמודות מה-SHP שנרצה לתרגם לעברית
RENAME_COLUMNS = {
    "NUM"        : "מספר תא שטח",
    "MAVAT_NAME" : "ייעוד",
    "MAVAT_CODE" : "קוד ייעוד",
    "LEGAL_AREA" : "שטח (דונם)",
    "SHAPE_AREA" : "שטח (מ\"ר)",
    "PLAN_NAME"  : "שם תכנית",
    "ADDRESS"    : "כתובת",
    "REMARKS"    : "הערות",
    "PLACE_NO"   : "מקום",
    "AGAM_ID"    : "מזהה AGAM",
    "STAGE"      : "שלב",
}

# מערכת קואורדינטות של ה-SHP
# ישראל: ITM = EPSG:2039  |  Old Israeli Grid = EPSG:28191
INPUT_CRS = "EPSG:2039"   # ← שנה אם צריך

# פלט (WGS84 נדרש לדפדפן)
OUTPUT_CRS = "EPSG:4326"

# פלט GeoJSON
OUTPUT_PATH = "data/parcels_merged.geojson"

# פלט קו כחול (גבול התכנית)
BOUNDARY_OUTPUT_PATH = "data/boundary.geojson"


# ===================================================================
#  טעינת SHP
# ===================================================================
def find_shp(path):
    """מוצא את קובץ ה-SHP — מעדיף PLAN (ייעודי קרקע)"""
    import glob
    if os.path.exists(path):
        return path
    all_shp = glob.glob("data/**/*.shp", recursive=True)
    # עדיפות 1: MVT_PLAN / MUT_PLAN (ייעודי הקרקע)
    plan_files = [f for f in all_shp if "PLAN" in os.path.basename(f).upper()
                  and "NUM" not in os.path.basename(f).upper()]
    if plan_files:
        print(f"   מצאתי ייעודי קרקע: {plan_files[0]}")
        return plan_files[0]
    if all_shp:
        print(f"   מצאתי SHP: {all_shp[0]}")
        return all_shp[0]
    return path


def load_shp(path):
    path = find_shp(path)
    if not os.path.exists(path):
        print(f"❌  קובץ SHP לא נמצא: {path}")
        print(f"   הנח את ה-SHP ב: {os.path.abspath('data/')}")
        sys.exit(1)

    print(f"⏳  טוען {path} ...")
    gdf = gpd.read_file(path)

    # הדפסת עמודות קיימות
    print(f"   נטענו {len(gdf)} תאי שטח")
    print(f"   עמודות ב-SHP: {list(gdf.columns)}")
    print(f"   מערכת קואורדינטות: {gdf.crs}")

    # תרגום שמות עמודות לעברית
    cols_to_rename = {k: v for k, v in RENAME_COLUMNS.items() if k in gdf.columns}
    if cols_to_rename:
        gdf = gdf.rename(columns=cols_to_rename)
        print(f"   תורגמו עמודות: {list(cols_to_rename.keys())}")

    return gdf


# ===================================================================
#  טעינת CSV
# ===================================================================
def load_csv(path):
    if not os.path.exists(path):
        print(f"⚠️   קובץ CSV לא נמצא: {path}")
        print(f"    ממשיך ללא נתוני בעלות (ניתן להוסיף מאוחר יותר)")
        return None

    print(f"⏳  טוען {path} ...")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str)
    print(f"   נטענו {len(df)} שורות")
    print(f"   עמודות ב-CSV: {list(df.columns)}")
    return df


# ===================================================================
#  המרת CRS
# ===================================================================
def reproject(gdf):
    if gdf.crs is None:
        print(f"⚠️   אין CRS מוגדר ב-SHP — מניח {INPUT_CRS}")
        gdf = gdf.set_crs(INPUT_CRS)
    elif str(gdf.crs) != INPUT_CRS:
        print(f"   מזוהה: {gdf.crs}")

    print(f"⏳  ממיר לקואורדינטות WGS84 (EPSG:4326)...")
    return gdf.to_crs(OUTPUT_CRS)


# ===================================================================
#  מיזוג CSV
# ===================================================================
def merge_csv(gdf, df):
    if df is None:
        return gdf, 0

    # ניקוי מפתחות
    join_col = "מספר תא שטח"  # אחרי התרגום
    gdf[join_col]  = gdf[join_col].astype(str).str.strip()
    df[CSV_PARCEL_KEY] = df[CSV_PARCEL_KEY].astype(str).str.strip()

    # אם שם העמודה ב-CSV שונה, נשנה את שמה לפני המיזוג
    if CSV_PARCEL_KEY != join_col:
        df = df.rename(columns={CSV_PARCEL_KEY: join_col})

    before = len(gdf)
    merged = gdf.merge(df, on=join_col, how="left", suffixes=("", "_csv"))

    # הסר עמודות כפולות מה-merge
    dup_cols = [c for c in merged.columns if c.endswith("_csv")]
    merged = merged.drop(columns=dup_cols)

    matched = merged[join_col].isin(df[join_col]).sum()
    print(f"   תואמו: {matched} / {before} תאי שטח")

    unmatched = merged[~merged[join_col].isin(df[join_col])][join_col].tolist()
    if unmatched:
        print(f"⚠️   {len(unmatched)} תאים ללא נתוני בעלות:")
        for u in unmatched[:5]:
            print(f"     · {u}")
        if len(unmatched) > 5:
            print(f"     ... ועוד {len(unmatched)-5}")

    return merged, matched


# ===================================================================
#  שמירת GeoJSON
# ===================================================================
def save_geojson(gdf, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    print(f"⏳  שומר {path} ...")
    gdf.to_file(path, driver="GeoJSON", encoding="utf-8")
    size_kb = os.path.getsize(path) / 1024
    print(f"   גודל: {size_kb:.1f} KB")


# ===================================================================
#  הצגת שדות
# ===================================================================
def print_fields(gdf):
    print("\n📋  שדות בקובץ הסופי:")
    for col in gdf.columns:
        if col == "geometry":
            continue
        sample = gdf[col].dropna().head(1).tolist()
        sample_val = sample[0] if sample else "—"
        print(f"    {col:<35} לדוגמה: {sample_val}")


# ===================================================================
#  ייצוא קו כחול (גבול התכנית) — MVT_GVUL
# ===================================================================
def export_boundary():
    """מחפש את קובץ MVT_GVUL.shp ומייצא אותו כ-GeoJSON"""
    import glob
    gvul_files = [f for f in glob.glob("data/**/*.shp", recursive=True)
                  if "GVUL" in os.path.basename(f).upper()]
    if not gvul_files:
        print("⚠️   לא נמצא קובץ גבול (MVT_GVUL.shp) — ממשיך בלעדיו")
        return

    path = gvul_files[0]
    print(f"\n⏳  טוען קו כחול: {path} ...")
    gdf = gpd.read_file(path)
    print(f"   נטענו {len(gdf)} אובייקטי גבול")

    # המרת CRS
    if gdf.crs is None:
        gdf = gdf.set_crs(INPUT_CRS)
    gdf = gdf.to_crs(OUTPUT_CRS)

    save_geojson(gdf, BOUNDARY_OUTPUT_PATH)
    print(f"   ✅  קו כחול נשמר: {os.path.abspath(BOUNDARY_OUTPUT_PATH)}")


# ===================================================================
#  הפעלה ראשית
# ===================================================================
def main():
    print("=" * 55)
    print("  ממיר SHP + CSV → GeoJSON אינטרקטיבי")
    print("=" * 55)

    gdf = load_shp(SHP_PATH)
    gdf = reproject(gdf)

    df = load_csv(CSV_PATH)
    if df is not None:
        gdf, matched = merge_csv(gdf, df)

    save_geojson(gdf, OUTPUT_PATH)
    print_fields(gdf)

    # ייצוא קו כחול (גבול תכנית)
    export_boundary()

    print("\n✅  סיום!")
    print(f"   קובץ מוכן: {os.path.abspath(OUTPUT_PATH)}")
    print(f"\n   ▶  כעת הפעל שרת מקומי:")
    print(f"      python -m http.server 8000")
    print(f"   ▶  ופתח בדפדפן:")
    print(f"      http://localhost:8000")
    print()


if __name__ == "__main__":
    main()
