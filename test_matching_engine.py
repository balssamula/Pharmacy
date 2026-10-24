import unittest
import pandas as pd
from matching_engine import normalize_sku, parse_price, parse_tax, compare_catalogs

C = ["رقم المنتج", "اسم المنتج", "سعر المنتج", "خاضع للضريبة؟"]

def frame(rows, category=None):
    df = pd.DataFrame(rows, columns=C)
    if category is not None:
        df["التصنيف"] = category
    return df

class TestMatching(unittest.TestCase):
    def test_sku_format(self):
        self.assertEqual(normalize_sku(19429.0), "19429")
        self.assertEqual(normalize_sku("٠٠١٢٣"), "00123")
        self.assertEqual(normalize_sku("00123"), "00123")
        self.assertNotEqual(normalize_sku("00123"), normalize_sku(123))

    def test_tax_and_price(self):
        self.assertIs(parse_tax("لا"), False)
        self.assertIs(parse_tax("غير خاضع"), False)
        self.assertIs(parse_tax("نعم"), True)
        self.assertIsNone(parse_tax("؟"))
        self.assertEqual(str(parse_price("١٬٢٣٤٫٥٠")), "1234.50")
        self.assertIsNone(parse_price("broken"))

    def test_sections(self):
        salla = frame([
            ["001", "واحد", "10.00", "نعم"], ["002", "اسم سلة", 11.50, "نعم"],
            ["004", "حصري", 2, "نعم"],
        ])
        system = frame([
            ["001", "واحد", "10.01", "نعم"], ["002", "اسم نظام", 15.0, "لا"],
            ["003", "جديد", 22.0, "نعم"],
        ])
        out = compare_catalogs(salla, system)
        self.assertEqual(out["summary"]["new_products"], 1)
        self.assertEqual(out["summary"]["salla_only"], 1)
        self.assertEqual(out["summary"]["different_names"], 1)
        self.assertEqual(out["summary"]["different_prices"], 1)
        self.assertEqual(out["summary"]["different_taxes"], 1)
        self.assertEqual(out["names"].iloc[0]["SKU"], "002")

    def test_duplicate_quarantine(self):
        salla = frame([["1", "أ", 10, "نعم"], ["1", "ب", 15, "لا"], [None, "تائه", 4, "نعم"]])
        system = frame([["1", "ج", 18, "نعم"], ["2", "جديد", 3, "نعم"]])
        out = compare_catalogs(salla, system)
        self.assertEqual(out["summary"]["ambiguous_skus"], 1)
        self.assertEqual(out["summary"]["new_products"], 1)
        self.assertGreaterEqual(out["summary"]["problems"], 3)
        self.assertEqual(out["summary"]["comparable_common_skus"], 0)

    def test_invalid_new_not_uploadable(self):
        out=compare_catalogs(frame([]), frame([["1", "بلا سعر", 0, "لا"],["2", "مجهول", 7, "؟"]]))
        self.assertEqual(out["summary"]["new_products"],2)
        self.assertEqual(out["summary"]["ready_to_upload"],0)

    def test_excluded_category(self):
        s=frame([["1", "a", 9, "نعم"]])
        sys=frame([["1", "a", 9, "نعم"]],category=["MEDICINE"])
        out=compare_catalogs(s,sys,excluded_categories="MEDICINE")
        self.assertEqual(out["summary"]["excluded_system_rows"],1)
        self.assertEqual(out["summary"]["salla_only"],0)


class TestRequestedEnhancements(unittest.TestCase):
    def test_pack_changes(self):
        from matching_engine import classify_pack_difference
        grams = classify_pack_difference('شامبو 100 جرام', 'شامبو 60 جم')
        self.assertIn('اختلاف وزن فقط', grams['نوع اختلاف الاسم'])
        count = classify_pack_difference('فيتامين 18 حبة', 'فيتامين 21 حبة')
        self.assertIn('اختلاف عدد فقط', count['نوع اختلاف الاسم'])
        liters = classify_pack_difference('غسول 1 لتر', 'غسول 1000 مل')
        self.assertEqual(liters['نوع اختلاف الاسم'], 'اختلاف نص الاسم')
        self.assertEqual(classify_pack_difference('منتج X100 MODEL', 'منتج X200 MODEL')['نوع اختلاف الاسم'], 'اختلاف نص الاسم')
        dose = classify_pack_difference('قوة 100mg', 'قوة 200mg')
        self.assertIn('تركيز/جرعة', dose['نوع اختلاف الاسم'])

    def test_exclusion_is_tab_specific(self):
        salla = frame([["001", "شامبو 60 مل", 10, "نعم"], ["002", "حلوى 21 حبة", 10, "نعم"]])
        system = frame([["001", "شامبو 100 مل", 20, "لا"], ["002", "حلوى 18 حبة", 11, "نعم"]])
        out = compare_catalogs(salla, system, excluded_name_skus=["001"], excluded_price_skus=["002"])
        self.assertEqual(out['summary']['different_names'], 1)
        self.assertEqual(out['summary']['size_count_differences'], 1)
        self.assertEqual(out['summary']['different_prices'], 1)
        self.assertEqual(out['summary']['different_taxes'], 1)
        self.assertEqual(out['prices'].iloc[0]['SKU'], '001')
        self.assertEqual(out['names'].iloc[0]['SKU'], '002')
        self.assertEqual(out['summary']['name_exclusions_applied'], 1)
        self.assertEqual(out['summary']['price_exclusions_applied'], 1)

    def test_full_report_export(self):
        import zipfile
        from io import BytesIO
        from matching_export import build_full_reconciliation_excel
        out = compare_catalogs(frame([["001", "شامبو 60 مل", 10, "نعم"]]), frame([["001", "شامبو 100 مل", 15, "لا"]]))
        binary = build_full_reconciliation_excel(out)
        with zipfile.ZipFile(BytesIO(binary)) as z:
            self.assertEqual(z.testzip(), None)
            names = [n for n in z.namelist() if n.startswith('xl/worksheets/sheet') and n.endswith('.xml')]
            self.assertEqual(len(names), 10)

if __name__ == "__main__":
    unittest.main()
