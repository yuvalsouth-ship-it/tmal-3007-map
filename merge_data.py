"""
merge_data.py
-------------
ממזג קובץ GeoJSON של תאי שטח עם קובץ CSV של נתוני בעלות.
המפתח המחבר: "מספר תא שטח"

שימוש:
    python merge_data.py

קלט:
    data/parcels.geojson  — תאי השטח מ-QGIS
    data/ownership.csv    — נתוני הבעלות

פלט:
    data/parcels_merged.geojson — קובץ מאוחד לטעינה במפה
"""

import json
import csv
import os
import sys

INPUT_GEOJSON = "data/parcels.geojson"
INPUT_CSV     = "data/ownership.csv"
OUTPUT_GEOJSON = "data/parcels_merged.geojson"

JOIN_KEY = "מספר תא שטח"  # שם העמודה המשותפת


def load_geojson(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_csv(path):
    rows = {}
    with open(path, "r", encoding="utf-8-sig") as f:  # utf-8-sig מטפל ב-BOM של Excel
        reader = csv.DictReader(f)
        for row in reader:
            key = str(row.get(JOIN_KEY, "")).strip()
            if key:
                rows[key] = row
    return rows


def merge(geojson, csv_data):
    matched = 0
    unmatched = []

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})
        parcel_num = str(props.get(JOIN_KEY, "")).strip()

        if parcel_num in csv_data:
            props.update(csv_data[parcel_num])
            matched += 1
        else:
            unmatched.append(parcel_num)

    return geojson, matched, unmatched


def main():
    # בדיקת קבצים
    for path in [INPUT_GEOJSON, INPUT_CSV]:
        if not os.path.exists(path):
            print(f"❌  קובץ לא נמצא: {path}")
            sys.exit(1)

    print(f"⏳  טוען {INPUT_GEOJSON} ...")
    geojson = load_geojson(INPUT_GEOJSON)
    total_features = len(geojson.get("features", []))
    print(f"   נטענו {total_features} תאי שטח")

    print(f"⏳  טוען {INPUT_CSV} ...")
    csv_data = load_csv(INPUT_CSV)
    print(f"   נטענו {len(csv_data)} שורות מה-CSV")

    print(f"⏳  ממזג לפי עמודה: '{JOIN_KEY}' ...")
    merged_geojson, matched, unmatched = merge(geojson, csv_data)

    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(merged_geojson, f, ensure_ascii=False, indent=2)

    print(f"\n✅  הצליח! נשמר ב: {OUTPUT_GEOJSON}")
    print(f"   תואמו: {matched} / {total_features} תאים")

    if unmatched:
        print(f"\n⚠️   {len(unmatched)} תאים ללא נתוני בעלות:")
        for u in unmatched[:10]:
            print(f"     · {u if u else '(ריק)'}")
        if len(unmatched) > 10:
            print(f"     ... ועוד {len(unmatched) - 10}")


if __name__ == "__main__":
    main()
