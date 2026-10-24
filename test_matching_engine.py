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

if __name__ == "__main__":
    unittest.main()
