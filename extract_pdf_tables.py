"""
extract_pdf_tables.py
---------------------
מחלץ טבלאות זכויות בנייה מתוך PDF של תדפיס הוראות התכנית.
שומר כ-JSON לשימוש בעמוד הנחיתה.

מטפל בבעיית טקסט עברי הפוך (visual order) ב-PDF.

התקנה (פעם אחת):
    pip install pdfplumber

שימוש:
    python extract_pdf_tables.py

בסיום ייווצר: data/building_rights.json
"""

import sys
import os
import json
import re
import unicodedata
from datetime import datetime

# ── ייבוא pdfplumber ─────────────────────────────────────────────
try:
    import pdfplumber
except ImportError:
    print("❌  חסר: pdfplumber")
    print("   הרץ: pip install pdfplumber")
    sys.exit(1)


# ===================================================================
#  ⚙️  הגדרות
# ===================================================================

PDF_PATH = None  # יזוהה אוטומטית
OUTPUT_PATH = "data/building_rights.json"

# מילות מפתח לזיהוי טבלאות זכויות (בסדר הנכון)
RIGHTS_KEYWORDS = [
    "זכויות", "בנייה", "בניה", "אחוזי", "קומות", "תא שטח", "תאי שטח",
    "שטח עיקרי", "שטח שירות", "יחידות", "שימושים",
    "ייעוד", "מותר", "צפיפות", "חלקות", "גוש", "חלקה",
    "סימון בתשריט", "הנחיות מיוחדות", "מספר גוש",
]

# מילים מוכרות בעברית — לזיהוי אם הטקסט הפוך
KNOWN_HEBREW_WORDS = [
    "ייעוד", "גוש", "חלקה", "שטח", "בנייה", "בניה", "קומות", "זכויות",
    "מגורים", "תעסוקה", "מסחר", "ציבורי", "דרך", "תכנית", "הוראות",
    "סימון", "תשריט", "שימושים", "מותר", "חלקות", "מספר",
]


# ===================================================================
#  תיקון טקסט עברי הפוך (Visual Order → Logical Order)
# ===================================================================
def is_hebrew_char(ch):
    """בודק אם תו הוא עברי"""
    return '\u0590' <= ch <= '\u05FF' or '\uFB1D' <= ch <= '\uFB4F'


def has_hebrew(text):
    """בודק אם מחרוזת מכילה תווים עבריים"""
    return any(is_hebrew_char(c) for c in text)


def detect_reversed_hebrew(text):
    """
    בודק אם טקסט עברי מאוחסן בסדר הפוך (visual order).
    משווה את המחרוזת ואת ההיפוך שלה למילים מוכרות.
    """
    if not has_hebrew(text):
        return False

    reversed_text = text[::-1]

    # בדיקה: האם ההיפוך מכיל יותר מילים מוכרות?
    score_original = sum(1 for w in KNOWN_HEBREW_WORDS if w in text)
    score_reversed = sum(1 for w in KNOWN_HEBREW_WORDS if w in reversed_text)

    return score_reversed > score_original


def fix_hebrew_text(text):
    """
    מתקן טקסט עברי הפוך.
    שומר מספרים וסימנים באנגלית בסדר הנכון.
    """
    if not text or not has_hebrew(text):
        return text

    # פיצול לקטעים: עברי vs לא-עברי (מספרים, אנגלית, סימנים)
    segments = []
    current = ""
    current_is_hebrew = None

    for ch in text:
        ch_hebrew = is_hebrew_char(ch)
        if current_is_hebrew is None:
            current_is_hebrew = ch_hebrew

        if ch_hebrew == current_is_hebrew or ch in " \t":
            current += ch
        else:
            segments.append((current, current_is_hebrew))
            current = ch
            current_is_hebrew = ch_hebrew

    if current:
        segments.append((current, current_is_hebrew))

    # היפוך סדר הקטעים + היפוך תוכן הקטעים העבריים
    result_parts = []
    for seg_text, seg_is_hebrew in reversed(segments):
        if seg_is_hebrew:
            result_parts.append(seg_text[::-1])
        else:
            result_parts.append(seg_text.strip())

    result = " ".join(p for p in result_parts if p)
    # ניקוי רווחים כפולים
    result = re.sub(r'\s+', ' ', result).strip()
    return result


def fix_text_if_needed(text, is_reversed_pdf):
    """מתקן טקסט אם ה-PDF הפוך"""
    if not text or not is_reversed_pdf:
        return text
    if not has_hebrew(text):
        return text
    return fix_hebrew_text(text)


# ===================================================================
#  חיפוש PDF אוטומטי
# ===================================================================
def find_pdf():
    import glob
    pdf_files = glob.glob("data/*.pdf") + glob.glob("data/**/*.pdf", recursive=True)
    if not pdf_files:
        return None
    for pf in pdf_files:
        name = os.path.basename(pf)
        if "הוראות" in name or "תדפיס" in name:
            return pf
    return pdf_files[0]


# ===================================================================
#  ניקוי תא
# ===================================================================
def clean_cell(val):
    if val is None:
        return ""
    val = str(val).strip()
    val = " ".join(val.split())
    return val


# ===================================================================
#  חילוץ טבלאות
# ===================================================================
def extract_tables(pdf_path):
    print(f"⏳  פותח {pdf_path} ...")

    all_tables = []
    all_raw_tables = []

    with pdfplumber.open(pdf_path) as pdf:
        print(f"   {len(pdf.pages)} עמודים ב-PDF")

        for i, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            if not tables:
                continue

            for t_idx, table in enumerate(tables):
                if not table or len(table) < 2:
                    continue

                all_raw_tables.append({
                    "page": i + 1,
                    "table_index": t_idx,
                    "rows": len(table),
                    "cols": len(table[0]) if table[0] else 0,
                    "header_sample": [clean_cell(c) for c in (table[0] or [])[:5]],
                })

                all_tables.append({
                    "page": i + 1,
                    "table_index": t_idx,
                    "data": table,
                })

    return all_tables, all_raw_tables


# ===================================================================
#  זיהוי אם ה-PDF הפוך
# ===================================================================
def detect_pdf_direction(tables):
    """
    בודק את כל הכותרות בטבלאות כדי לקבוע אם ה-PDF הפוך.
    """
    all_header_text = ""
    for t in tables:
        for row in t["data"][:2]:  # שורה ראשונה ושנייה
            if row:
                all_header_text += " " + " ".join(clean_cell(c) for c in row)

    if detect_reversed_hebrew(all_header_text):
        print("🔄  זוהה טקסט עברי הפוך — מתקן אוטומטית!")
        return True
    else:
        print("   כיוון טקסט: תקין")
        return False


# ===================================================================
#  זיהוי טבלת זכויות (עובד גם עם טקסט מתוקן)
# ===================================================================
def is_rights_table(headers_text):
    score = sum(1 for kw in RIGHTS_KEYWORDS if kw in headers_text)
    return score >= 2


# ===================================================================
#  עיבוד טבלאות
# ===================================================================
def process_tables(tables, is_reversed):
    parcels = {}
    parcel_uses = {}    # parcel_id → [{use-specific fields}]
    all_columns = set()
    processed_count = 0
    tables_used = 0

    # מפתחות אפשריים לתא שטח (אחרי תיקון)
    parcel_key_options = [
        "תאי שטח", "תא שטח", "מספר תא שטח", "חלקות מספרי בחלקן",
        "מספרי חלקות בחלקן", "חלקות", "מס' תא שטח",
    ]

    # שדות שמציינים טבלת זכויות עם נתוני שימוש
    RIGHTS_TABLE_MARKERS = ["שימוש", "גודל מגרש", "שטחי בני"]

    # שדות שמציינים את טבלת הזכויות הראשית (לא טבלאות טקסט קטנות)
    # צריכים לפחות 2 מתוך אלו + לפחות 5 עמודות
    MAIN_RIGHTS_MARKERS = ["קומות", "שטחי בני", "גודל מגרש"]
    MIN_COLS_FOR_RIGHTS = 5

    # שדות ספציפיים לשימוש — אלו נכנסים למערך uses
    USE_FIELD_PATTERNS = [
        "שימוש",
        "קומות",           # catches: קומות מעל/מתחת, מקסימום מספר קומות
        "מספר יח",
        "שטחי בני",        # catches: שטחי בנייה מעל/מתחת
        "גודל מגרש",
        "בניין",
    ]

    # מיפוי עמודות חסרות שם / שמות לא מדויקים בטבלת הזכויות הראשית
    # מבוסס על המבנה: יעוד | שימוש | תאי שטח | בניין/מקום | גודל מגרש |
    # שטחי בנייה מעל | שטחי בנייה מתחת | מספר יח"ד | קומות מעל | קומות מתחת
    RIGHTS_COLUMN_RENAMES = {
        "עמודה_1": "קומות מעל הכניסה הקובעת",
        "עמודה_4": "שטחי בנייה מעל הכניסה הקובעת",
    }

    def is_use_field(field_name):
        """בודק אם שדה הוא ספציפי לשימוש (נכנס למערך uses)"""
        return any(p in field_name for p in USE_FIELD_PATTERNS)

    # שמירת כותרות טבלת זכויות לזיהוי דפי המשך
    saved_rights_headers = None
    saved_rights_col_count = None
    saved_rights_parcel_col_idx = None
    saved_rights_parcel_col_name = None

    for table_info in tables:
        table = table_info["data"]
        if len(table) < 2:
            continue

        # תיקון + ניקוי כותרות
        raw_headers = [clean_cell(h) for h in table[0]]
        headers = [fix_text_if_needed(h, is_reversed) for h in raw_headers]

        # ניקוי כותרות ריקות
        headers = [h if h else f"עמודה_{i}" for i, h in enumerate(headers)]

        # בדיקה אם זו טבלה רלוונטית
        headers_text = " ".join(headers)
        is_rights = is_rights_table(headers_text)

        # בדיקה אם זו טבלת זכויות עם עמודת שימוש
        is_use_table = any(marker in headers_text for marker in RIGHTS_TABLE_MARKERS)

        # ── זיהוי דפי המשך של טבלת הזכויות ──
        # כאשר pdfplumber מפצל טבלה רב-דפית, שורת הנתונים הראשונה
        # מתפרשת כ"כותרת" חדשה עם ערכים מספריים וכותרות ריקות.
        is_continuation = False
        data_rows = list(table[1:])  # ברירת מחדל: שורות 1+

        if (saved_rights_headers is not None
            and not is_use_table
            and len(headers) == saved_rights_col_count
            and len(headers) >= MIN_COLS_FOR_RIGHTS):
            # בדיקה: רוב הכותרות הן ריקות (עמודה_X) או מספריות
            unnamed = sum(1 for h in headers
                         if h.startswith("עמודה_") or re.match(r'^[\d,.\-\s]+$', h.strip()))
            if unnamed >= len(headers) // 2:
                is_continuation = True
                is_use_table = True
                # שורה 0 היא בעצם נתונים — מוסיפים אותה לרשימת הנתונים
                data_rows = [table[0]] + data_rows
                headers = saved_rights_headers

        # שמירת כותרות טבלת הזכויות הראשית (5+ עמודות, עם שדות בנייה)
        if (is_use_table
            and saved_rights_headers is None
            and not is_continuation
            and len(headers) >= MIN_COLS_FOR_RIGHTS):
            markers_found = sum(1 for m in MAIN_RIGHTS_MARKERS if m in headers_text)
            if markers_found >= 2:
                # שינוי שמות עמודות חסרות שם ותיקון שמות לא מדויקים
                for i, h in enumerate(headers):
                    if h in RIGHTS_COLUMN_RENAMES:
                        headers[i] = RIGHTS_COLUMN_RENAMES[h]
                    elif "מקסימום" in h and "קומות" in h:
                        headers[i] = "קומות מתחת לכניסה הקובעת"
                    elif "שטחי בני" in h and "מעל" not in h and "מתחת" not in h:
                        headers[i] = "שטחי בנייה מתחת לכניסה הקובעת"

                saved_rights_headers = headers[:]
                saved_rights_col_count = len(headers)
                print(f"     💾 נשמרו כותרות טבלת זכויות ראשית ({len(headers)} עמודות)")
                print(f"        {headers}")

        cont_label = '  🔗 המשך טבלה' if is_continuation else ''
        rows_count = len(data_rows)
        print(f"   עמוד {table_info['page']}, טבלה {table_info['table_index']}: "
              f"{rows_count} שורות × {len(headers)} עמודות"
              f"{'  ✓ זכויות' if is_rights else ''}"
              f"{'  📋 שימושים' if is_use_table else ''}"
              f"{cont_label}")
        if len(headers) <= 8:
            print(f"     כותרות: {headers}")
        else:
            print(f"     כותרות: {headers[:6]}...")

        if not is_continuation:
            all_columns.update(headers)
        tables_used += 1

        # מציאת עמודת מפתח
        parcel_col_idx = None
        parcel_col_name = None

        if is_continuation and saved_rights_parcel_col_idx is not None:
            # שימוש בעמודת מפתח ששמרנו מהטבלה הראשית
            parcel_col_idx = saved_rights_parcel_col_idx
            parcel_col_name = saved_rights_parcel_col_name
        else:
            for idx, h in enumerate(headers):
                for key_option in parcel_key_options:
                    if key_option in h:
                        parcel_col_idx = idx
                        parcel_col_name = h
                        break
                if parcel_col_idx is not None:
                    break

        # שמירת עמודת מפתח של טבלת הזכויות
        if is_use_table and not is_continuation and parcel_col_idx is not None:
            saved_rights_parcel_col_idx = parcel_col_idx
            saved_rights_parcel_col_name = parcel_col_name

        # עיבוד שורות
        for row in data_rows:
            if not row or all(not clean_cell(c) for c in row):
                continue

            # בניית מילון עם ערכים מתוקנים
            row_dict = {}
            for j, val in enumerate(row):
                if j < len(headers):
                    fixed_val = fix_text_if_needed(clean_cell(val), is_reversed)
                    if fixed_val:
                        row_dict[headers[j]] = fixed_val

            if not row_dict:
                continue

            # חיפוש מפתח תא שטח
            parcel_id = None

            # 1. לפי עמודה שזוהתה
            if parcel_col_idx is not None and parcel_col_name in row_dict:
                val = row_dict[parcel_col_name]
                # חילוץ מספרים בלבד (ייתכנו טווחים כמו "730-732")
                nums = re.findall(r'\d+', val)
                if nums:
                    parcel_id = nums[0]  # לוקח מספר ראשון

            # 2. fallback — עמודה ראשונה אם מספרית
            if not parcel_id:
                first_val = clean_cell(row[0]) if row else ""
                if first_val and re.match(r'^\d+$', first_val):
                    parcel_id = first_val

            if parcel_id:
                if is_use_table:
                    # ── טבלת שימושים: הפרדת שדות ──
                    use_entry = {}
                    common_entry = {}
                    for k, v in row_dict.items():
                        if is_use_field(k):
                            use_entry[k] = v
                        else:
                            common_entry[k] = v

                    # שדות כלליים — מיזוג
                    if parcel_id not in parcels:
                        parcels[parcel_id] = common_entry
                    else:
                        for k, v in common_entry.items():
                            if v and (k not in parcels[parcel_id] or not parcels[parcel_id][k]):
                                parcels[parcel_id][k] = v

                    # שדות שימוש — הוספה לרשימה
                    if use_entry:
                        if parcel_id not in parcel_uses:
                            parcel_uses[parcel_id] = []
                        parcel_uses[parcel_id].append(use_entry)
                else:
                    # ── טבלה רגילה: מיזוג שטוח ──
                    if parcel_id in parcels:
                        for k, v in row_dict.items():
                            if v and (k not in parcels[parcel_id] or not parcels[parcel_id][k]):
                                parcels[parcel_id][k] = v
                    else:
                        parcels[parcel_id] = row_dict

                processed_count += 1

    # שילוב שימושים לתוך החלקות
    for pid, uses in parcel_uses.items():
        if pid not in parcels:
            parcels[pid] = {}
        parcels[pid]["uses"] = uses

    print(f"\n   📋 {len(parcel_uses)} תאי שטח עם נתוני שימוש")
    multi = sum(1 for u in parcel_uses.values() if len(u) > 1)
    if multi:
        print(f"   📋 {multi} תאי שטח עם שימושים מרובים")

    return parcels, sorted(all_columns), processed_count


# ===================================================================
#  ניקוי — הסרת עמודות רעש (ערכים מאוד ארוכים שהם כנראה פסקאות)
# ===================================================================
def clean_parcels(parcels):
    """מנקה שדות שהם כנראה רעש (ארוכים מדי, מספרי עמודה וכד')"""

    def is_noise_key(k):
        if k.startswith("עמודה_"):
            return True
        if len(k) > 80:
            return True
        if re.match(r'^[\d\s,.\-/: ]+$', k) and len(k) > 15:
            return True
        return False

    cleaned = {}
    for pid, data in parcels.items():
        clean_data = {}
        for k, v in data.items():
            # טיפול מיוחד במערך uses
            if k == "uses":
                clean_uses = []
                for use in v:
                    clean_use = {uk: uv for uk, uv in use.items()
                                 if not is_noise_key(uk) and len(str(uv)) <= 300}
                    if clean_use:
                        clean_uses.append(clean_use)
                if clean_uses:
                    clean_data["uses"] = clean_uses
                continue

            if is_noise_key(k):
                continue
            if len(str(v)) > 300:
                continue
            clean_data[k] = v
        if clean_data:
            cleaned[pid] = clean_data
    return cleaned


# ===================================================================
#  שמירת JSON
# ===================================================================
def save_json(parcels, columns, pdf_path):
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)

    # סינון עמודות נקיות
    clean_cols = [c for c in columns
                  if not c.startswith("עמודה_")
                  and len(c) <= 80
                  and not (re.match(r'^[\d\s,.\-/: ]+$', c) and len(c) > 15)]

    output = {
        "metadata": {
            "source": os.path.basename(pdf_path),
            "extracted_at": datetime.now().isoformat(),
            "total_parcels": len(parcels),
            "total_columns": len(clean_cols),
        },
        "columns": clean_cols,
        "parcels": parcels,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    size_kb = os.path.getsize(OUTPUT_PATH) / 1024
    print(f"\n💾  נשמר: {OUTPUT_PATH} ({size_kb:.1f} KB)")


# ===================================================================
#  הפעלה ראשית
# ===================================================================
def main():
    print("=" * 55)
    print("  מחלץ טבלאות זכויות בנייה מ-PDF")
    print("=" * 55)

    pdf_path = PDF_PATH or find_pdf()
    if not pdf_path or not os.path.exists(pdf_path):
        print("❌  לא נמצא קובץ PDF בתיקיית data/")
        print(f"   הנח את ה-PDF ב: {os.path.abspath('data/')}")
        sys.exit(1)

    print(f"📄  קובץ: {os.path.basename(pdf_path)}")
    print(f"   גודל: {os.path.getsize(pdf_path)/1024:.0f} KB")
    print()

    # חילוץ
    all_tables, raw_summary = extract_tables(pdf_path)

    if not all_tables:
        print("❌  לא נמצאו טבלאות ב-PDF!")
        sys.exit(1)

    print(f"\n📊  נמצאו {len(all_tables)} טבלאות")

    # זיהוי כיוון טקסט
    is_reversed = detect_pdf_direction(all_tables)

    # עיבוד
    print(f"\n⏳  מעבד טבלאות...")
    parcels, columns, processed = process_tables(all_tables, is_reversed)

    # ניקוי רעש
    parcels = clean_parcels(parcels)

    print(f"\n📋  תוצאות:")
    print(f"   {len(parcels)} תאי שטח ייחודיים")
    print(f"   {processed} שורות עובדו")

    if parcels:
        sample_id = list(parcels.keys())[0]
        sample = parcels[sample_id]
        print(f"\n   דוגמה (תא שטח {sample_id}):")
        for k, v in list(sample.items())[:8]:
            print(f"     {k}: {v}")
        if len(sample) > 8:
            print(f"     ... ועוד {len(sample)-8} שדות")

    # שמירה
    save_json(parcels, columns, pdf_path)

    print(f"\n✅  סיום!")
    print(f"   כעת פתח: http://localhost:8000/landing.html")
    print()


if __name__ == "__main__":
    main()
