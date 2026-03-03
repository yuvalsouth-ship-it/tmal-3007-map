"""
inspect_shp.py
--------------
מסריק קובץ SHP ומציג את כל העמודות + דוגמאות ערכים.
הרץ אותו ראשון כדי לדעת מה יש בקובץ לפני המיזוג.

שימוש:
    python inspect_shp.py

אם יש כמה קבצי SHP, שנה את SHP_PATH למטה.
"""

import sys
import os
import glob

try:
    import geopandas as gpd
except ImportError:
    print("❌  חסר geopandas. הרץ:  pip install geopandas")
    sys.exit(1)


def find_shp_files(folder="data"):
    """חיפוש אוטומטי של כל קבצי SHP בתיקייה"""
    return glob.glob(f"{folder}/**/*.shp", recursive=True) + \
           glob.glob(f"{folder}/*.shp")


def inspect(path):
    print(f"\n{'='*60}")
    print(f"  📂  {os.path.basename(path)}")
    print(f"{'='*60}")

    gdf = gpd.read_file(path)

    print(f"  תאי שטח (שורות): {len(gdf)}")
    print(f"  סוג גיאומטריה  : {gdf.geometry.geom_type.unique().tolist()}")
    print(f"  מערכת קואורד'  : {gdf.crs}")
    print(f"  Bounding Box    : {gdf.total_bounds.round(2).tolist()}")
    print()
    print(f"  {'עמודה':<30} {'סוג':<12} {'דוגמה'}")
    print(f"  {'-'*30} {'-'*12} {'-'*20}")

    for col in gdf.columns:
        if col == "geometry":
            continue
        dtype = str(gdf[col].dtype)
        samples = gdf[col].dropna().astype(str).unique()[:3]
        sample_str = " | ".join(samples) if len(samples) > 0 else "—"
        print(f"  {col:<30} {dtype:<12} {sample_str}")

    print()
    return gdf


def main():
    # 1. חיפוש אוטומטי
    shp_files = find_shp_files("data")

    # 2. אם לא נמצא ב-data — חפש בתיקייה הנוכחית
    if not shp_files:
        shp_files = glob.glob("*.shp")

    if not shp_files:
        print("❌  לא נמצאו קבצי SHP")
        print()
        print("   העתק את קבצי ה-SHP לתוך תיקיית  data/")
        print("   (נדרשים: .shp  .dbf  .shx  — ואם יש גם .prj)")
        print()
        print(f"   תיקיית הפרויקט: {os.path.abspath('data')}")
        sys.exit(1)

    print(f"✅  נמצאו {len(shp_files)} קובצי SHP:\n")
    for p in shp_files:
        print(f"    · {p}")

    for path in shp_files:
        inspect(path)

    print("=" * 60)
    print("  💡  הנחיות הבאות:")
    print()
    print("  1. זהה את עמודת הייעוד (לדוגמה: 'YIUD', 'ייעוד', 'USE')")
    print("  2. זהה את מפתח החיבור ל-CSV ('מספר תא שטח', 'PARCEL_ID'...)")
    print("  3. עדכן את convert_shp.py:")
    print("       JOIN_KEY  = 'שם_העמודה'")
    print("  4. הרץ:  python convert_shp.py")
    print("=" * 60)


if __name__ == "__main__":
    main()
