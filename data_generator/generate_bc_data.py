"""
Synthetic Dynamics 365 Business Central-style data generator.

Two companies:
  CCG        - the main business (mobility & healthcare equipment)
  RIVERBEND  - an acquired business with its own customer and item numbering

Outputs CSV extracts the way an API pull would land them:
  bc_extract/full_2026-09-30/   full extract of every table
  bc_extract/incr_2026-10-01/   changed records only (by SystemModifiedAt), plus key snapshots
  bc_extract/incr_2026-10-02/
  bc_extract/incr_2026-10-03/
  reference/bc_control_totals.csv   what Business Central itself reports (reconciliation target)
  reference/answer_key.json         self-check numbers

Deterministic: same seed -> same data.
"""
import csv
import json
import os
import random
import uuid
import datetime as dt
from collections import defaultdict

random.seed(20261016)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
CUTOFF = dt.date(2026, 9, 30)
INCR_DAYS = [dt.date(2026, 10, 1), dt.date(2026, 10, 2), dt.date(2026, 10, 3)]


# ----------------------------------------------------------------- helpers
def sid():
    return str(uuid.UUID(int=random.getrandbits(128)))


def first_sunday(year, month):
    d = dt.date(year, month, 1)
    return d + dt.timedelta(days=(6 - d.weekday()) % 7)


def utc_offset(d):
    """Melbourne: AEDT (+11) from first Sunday of October to first Sunday of April, else AEST (+10)."""
    if d >= first_sunday(d.year, 10) or d < first_sunday(d.year, 4):
        return 11
    return 10


def ts(d, hour=None, minute=None):
    """Local Melbourne business time on date d, returned as a UTC ISO string (Business Central stores UTC)."""
    hour = random.randint(8, 18) if hour is None else hour
    minute = random.randint(0, 59) if minute is None else minute
    local = dt.datetime(d.year, d.month, d.day, hour, minute, random.randint(0, 59))
    utc = local - dt.timedelta(hours=utc_offset(d))
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def daterange(a, b):
    d = a
    while d <= b:
        yield d
        d += dt.timedelta(days=1)


def money(x):
    return round(x + 1e-9, 2)


def write_csv(path, rows, columns):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in columns})


# ----------------------------------------------------------------- columns
COLS = {
    "customer": ["Company", "No", "Name", "Customer_Type", "ABN", "Email", "Phone", "Address", "City",
                 "State", "Post_Code", "Global_Dimension_1_Code", "Customer_Posting_Group", "Blocked",
                 "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "vendor": ["Company", "No", "Name", "ABN", "City", "State", "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "item": ["Company", "No", "Description", "Item_Category_Code", "GTIN", "Base_Unit_of_Measure",
             "Unit_Price", "Unit_Cost", "VAT_Prod_Posting_Group", "Vendor_No", "Blocked",
             "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "location": ["Company", "Code", "Name", "Location_Type", "City", "State",
                 "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "sales_header": ["Company", "Document_Type", "No", "Sell_to_Customer_No", "Order_Date", "Location_Code",
                     "Status", "Salesperson_Code", "Global_Dimension_1_Code", "Global_Dimension_2_Code",
                     "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "sales_line": ["Company", "Document_Type", "Document_No", "Line_No", "Type", "No", "Description",
                   "Location_Code", "Quantity", "Unit_Price", "Line_Discount_Pct", "Amount",
                   "Amount_Including_VAT", "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "sales_invoice_header": ["Company", "No", "Order_No", "Sell_to_Customer_No", "Order_Date", "Posting_Date",
                             "Location_Code", "Salesperson_Code", "Global_Dimension_1_Code",
                             "Global_Dimension_2_Code", "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "sales_invoice_line": ["Company", "Document_No", "Line_No", "Type", "No", "Description", "Location_Code",
                           "Quantity", "Unit_Price", "Line_Discount_Pct", "Amount", "Amount_Including_VAT",
                           "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "sales_cr_memo_header": ["Company", "No", "Applies_to_Doc_No", "Sell_to_Customer_No", "Posting_Date",
                             "Return_Reason_Code", "Location_Code", "Global_Dimension_1_Code",
                             "Global_Dimension_2_Code", "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "sales_cr_memo_line": ["Company", "Document_No", "Line_No", "Type", "No", "Description", "Location_Code",
                           "Quantity", "Unit_Price", "Line_Discount_Pct", "Amount", "Amount_Including_VAT",
                           "SystemId", "SystemCreatedAt", "SystemModifiedAt"],
    "item_ledger_entry": ["Company", "Entry_No", "Item_No", "Posting_Date", "Entry_Type", "Document_Type",
                          "Document_No", "Location_Code", "Quantity", "SystemId", "SystemCreatedAt",
                          "SystemModifiedAt"],
}
KEYS_COLS = ["Company", "Document_Type", "No"]

# ----------------------------------------------------------------- reference data
COMPANIES = {
    "CCG": {"start": dt.date(2025, 7, 1), "orders_per_day": 7, "cust": 300, "item_prefix": "ITM-",
            "cust_prefix": "C", "inv_prefix": "PSI-", "ord_prefix": "SO-", "cm_prefix": "PSCM-"},
    "RIVERBEND": {"start": dt.date(2025, 1, 1), "orders_per_day": 3, "cust": 120, "item_prefix": "RB",
                  "cust_prefix": "C", "inv_prefix": "INV", "ord_prefix": "ORD", "cm_prefix": "CR"},
}

LOCATIONS = {
    "CCG": [("MEL-SHOW", "Melbourne Showroom", "SHOWROOM", "Melbourne", "VIC"),
            ("BEN-SHOW", "Bendigo Showroom", "SHOWROOM", "Bendigo", "VIC"),
            ("MIL-SHOW", "Mildura Showroom", "SHOWROOM", "Mildura", "VIC"),
            ("ECH-SHOW", "Echuca Showroom", "SHOWROOM", "Echuca", "VIC"),
            ("WOL-SHOW", "Wollongong Showroom", "SHOWROOM", "Wollongong", "NSW"),
            ("MEL-WH", "Melbourne Warehouse", "WAREHOUSE", "Dandenong", "VIC")],
    "RIVERBEND": [("GEELONG", "Geelong Store", "SHOWROOM", "Geelong", "VIC"),
                  ("BALLARAT", "Ballarat Store", "SHOWROOM", "Ballarat", "VIC"),
                  ("MAIN", "Main Warehouse", "WAREHOUSE", "Geelong", "VIC")],
}

REGION_BY_CITY = {
    "Melbourne": "METRO_VIC", "Dandenong": "METRO_VIC", "Frankston": "METRO_VIC", "Box Hill": "METRO_VIC",
    "Bendigo": "REGIONAL_VIC", "Mildura": "REGIONAL_VIC", "Echuca": "REGIONAL_VIC", "Geelong": "REGIONAL_VIC",
    "Ballarat": "REGIONAL_VIC", "Shepparton": "REGIONAL_VIC", "Wollongong": "NSW", "Albury": "NSW",
    "Sydney": "NSW",
}
CITIES = [("Melbourne", "VIC", "3000"), ("Dandenong", "VIC", "3175"), ("Frankston", "VIC", "3199"),
          ("Box Hill", "VIC", "3128"), ("Bendigo", "VIC", "3550"), ("Mildura", "VIC", "3500"),
          ("Echuca", "VIC", "3564"), ("Geelong", "VIC", "3220"), ("Ballarat", "VIC", "3350"),
          ("Shepparton", "VIC", "3630"), ("Wollongong", "NSW", "2500"), ("Albury", "NSW", "2640"),
          ("Sydney", "NSW", "2000")]

# (category, base names, price range excl GST, GST group)
CATALOGUE = [
    ("WHEELCHAIR", ["Self-Propelled Wheelchair", "Transit Wheelchair", "Lightweight Folding Wheelchair",
                    "Bariatric Wheelchair", "Tilt-in-Space Wheelchair"], (380, 4200), "GST_FREE"),
    ("SCOOTER", ["Mobility Scooter 3-Wheel", "Mobility Scooter 4-Wheel", "Travel Scooter"], (1800, 6500), "GST_FREE"),
    ("WALKING", ["Four-Wheel Walker", "Walking Frame", "Quad Walking Stick", "Folding Walking Stick",
                 "Forearm Crutches"], (25, 650), "GST_FREE"),
    ("BED", ["Electric Hospital Bed", "Low-Low Bed", "Bed Rail Set", "Pressure Mattress"], (240, 5200), "GST_FREE"),
    ("LIFTER", ["Patient Lifter", "Standing Hoist", "Lifter Sling Medium", "Lifter Sling Large"], (180, 4800), "GST_FREE"),
    ("SEATING", ["Lift Recliner Chair", "Day Chair", "Shower Chair", "Over-Toilet Frame"], (90, 3200), "GST10"),
    ("BATHROOM", ["Grab Rail 600mm", "Bath Board", "Raised Toilet Seat", "Shower Stool"], (35, 290), "GST10"),
    ("CUSHION", ["Gel Pressure Cushion", "Air Cell Cushion", "Foam Wedge Cushion"], (45, 780), "GST_FREE"),
    ("DAILY_LIVING", ["Reacher Grabber", "Sock Aid", "Over-Bed Table", "Pill Organiser"], (12, 260), "GST10"),
]
BRANDS = ["Aspire", "Kmed", "Invacare", "Pride", "Drive", "Peak Care", "Days", "Breezi"]

VENDORS = [("V0001", "Aspire Healthcare Supplies"), ("V0002", "Southern Medical Imports"),
           ("V0003", "Peak Care Distribution"), ("V0004", "Mobility Wholesale Co"),
           ("V0005", "Comfort Seating Australia"), ("V0006", "BathSafe Products"),
           ("V0007", "Lifting Solutions Pty Ltd"), ("V0008", "Daily Aids Direct")]

FIRST = ["Margaret", "John", "Patricia", "Robert", "Helen", "Peter", "Susan", "David", "Barbara", "Michael",
         "Joan", "Graham", "Dorothy", "Kevin", "Judith", "Ian", "Carol", "Brian", "Elaine", "Ross", "Priya",
         "Wei", "Maria", "Giuseppe", "Anh", "Mohammed", "Fatima", "Rahul", "Mei", "Sofia"]
LAST = ["Smith", "Jones", "Williams", "Brown", "Wilson", "Taylor", "Nguyen", "Anderson", "Thompson", "White",
        "Martin", "Kelly", "Ryan", "Walker", "Harris", "Lee", "Clarke", "Murphy", "Rossi", "Patel", "Chen",
        "Singh", "Papadopoulos", "Tran", "OBrien", "Campbell", "Hughes", "Morris", "Ward", "Bell"]
FACILITY_WORDS = ["Riverside", "Banksia", "Wattle", "Eucalypt", "Southern Cross", "Bayview", "Hillcrest",
                  "Lakeside", "Golden Grove", "Sunnyhill", "Murray", "Grampians", "Bellarine", "Coastal"]
STREETS = ["High St", "Main Rd", "Station St", "Church St", "Victoria Rd", "King St", "Queen St",
           "Murray Ave", "Elm Ct", "Park Rd"]

CUSTOMER_TYPES = [  # type, weight, posting group, business unit (Global Dimension 2)
    ("RETAIL", 45, "DOMESTIC", "RETAIL"),
    ("NDIS", 20, "NDIS", "HEALTHCARE"),
    ("DVA", 10, "GOVT", "HEALTHCARE"),
    ("AGED_CARE", 12, "TRADE", "HEALTHCARE"),
    ("HOSPITAL", 5, "GOVT", "HEALTHCARE"),
    ("RESELLER", 8, "TRADE", "WHOLESALE"),
]
BU_BY_TYPE = {t[0]: t[3] for t in CUSTOMER_TYPES}
SALESPEOPLE = ["JLEE", "MSMITH", "PNGUYEN", "AKELLY", "RPATEL"]


def gen_abn():
    return "".join(str(random.randint(0, 9)) for _ in range(11))


def gen_gtin():
    return "93" + "".join(str(random.randint(0, 9)) for _ in range(11))


# ----------------------------------------------------------------- state
data = {c: defaultdict(list) for c in COMPANIES}   # data[company][table] -> list of rows (full-extract truth)
truth_invoices = []      # (company, posting_date, amount) final truth for control totals
truth_cms = []
counters = defaultdict(int)


def next_no(company, kind, width=6):
    counters[(company, kind)] += 1
    cfg = COMPANIES[company]
    prefix = {"ord": cfg["ord_prefix"], "inv": cfg["inv_prefix"], "cm": cfg["cm_prefix"]}[kind]
    return f"{prefix}{counters[(company, kind)]:0{width}d}"


def next_entry(company):
    counters[(company, "ile")] += 1
    return counters[(company, "ile")]


# ----------------------------------------------------------------- master data
def build_vendors():
    for company in COMPANIES:
        for no, name in VENDORS:
            created = dt.date(2024, 1, random.randint(2, 28))
            city, state, _ = random.choice(CITIES)
            data[company]["vendor"].append({
                "Company": company, "No": no, "Name": name, "ABN": gen_abn(), "City": city, "State": state,
                "SystemId": sid(), "SystemCreatedAt": ts(created), "SystemModifiedAt": ts(created)})


def build_locations():
    for company, locs in LOCATIONS.items():
        for code, name, ltype, city, state in locs:
            created = dt.date(2024, 1, 2)
            data[company]["location"].append({
                "Company": company, "Code": code, "Name": name, "Location_Type": ltype, "City": city,
                "State": state, "SystemId": sid(), "SystemCreatedAt": ts(created),
                "SystemModifiedAt": ts(created)})


master_products = []  # shared real-world products: (description, category, gtin, price, cost, gst, vendor)


def build_items():
    for category, names, (lo, hi), gst in CATALOGUE:
        for base in names:
            for _ in range(random.randint(4, 6)):
                brand = random.choice(BRANDS)
                variant = random.choice(["Standard", "Deluxe", "Compact", "XL", "Classic", "Pro"])
                price = money(random.uniform(lo, hi))
                cost = money(price * random.uniform(0.52, 0.7))
                master_products.append((f"{brand} {base} {variant}", category, gen_gtin(), price, cost, gst,
                                        random.choice(VENDORS)[0]))
    random.shuffle(master_products)

    # CCG carries most products
    ccg_products = master_products[:120]
    for i, (desc, cat, gtin, price, cost, gst, vendor) in enumerate(ccg_products, start=1):
        created = dt.date(2024, random.randint(1, 12), random.randint(1, 28))
        data["CCG"]["item"].append({
            "Company": "CCG", "No": f"ITM-{10000 + i}", "Description": desc, "Item_Category_Code": cat,
            "GTIN": gtin, "Base_Unit_of_Measure": "EA", "Unit_Price": price, "Unit_Cost": cost,
            "VAT_Prod_Posting_Group": gst, "Vendor_No": vendor, "Blocked": "false",
            "SystemId": sid(), "SystemCreatedAt": ts(created), "SystemModifiedAt": ts(created)})

    # Riverbend: 40 of the same real products (same GTIN, different item no, different wording/category codes)
    # plus 20 products CCG does not carry
    rb_cat = {"WHEELCHAIR": "CHAIRS", "SCOOTER": "SCOOTERS", "WALKING": "WALK_AIDS", "BED": "BEDS",
              "LIFTER": "HOISTS", "SEATING": "CHAIRS", "BATHROOM": "BATH", "CUSHION": "PRESSURE",
              "DAILY_LIVING": "ADL"}
    shared = random.sample(ccg_products, 40)
    extra = master_products[120:140]
    for i, (desc, cat, gtin, price, cost, gst, vendor) in enumerate(shared + extra, start=1):
        created = dt.date(2023, random.randint(1, 12), random.randint(1, 28))
        rb_desc = desc.upper() if i % 3 == 0 else desc.replace("Wheelchair", "W/Chair").replace("Walking", "Walk")
        rb_price = money(price * random.uniform(0.95, 1.08))
        data["RIVERBEND"]["item"].append({
            "Company": "RIVERBEND", "No": f"RB{500 + i}", "Description": rb_desc,
            "Item_Category_Code": rb_cat[cat], "GTIN": gtin, "Base_Unit_of_Measure": "EACH",
            "Unit_Price": rb_price, "Unit_Cost": money(rb_price * random.uniform(0.55, 0.72)),
            "VAT_Prod_Posting_Group": gst, "Vendor_No": vendor, "Blocked": "false",
            "SystemId": sid(), "SystemCreatedAt": ts(created), "SystemModifiedAt": ts(created)})


def make_customer(company, no, created, ctype=None):
    ctype = ctype or random.choices([t[0] for t in CUSTOMER_TYPES], [t[1] for t in CUSTOMER_TYPES])[0]
    posting = {t[0]: t[2] for t in CUSTOMER_TYPES}[ctype]
    city, state, pc = random.choice(CITIES)
    if ctype in ("RETAIL", "NDIS", "DVA"):
        first, last = random.choice(FIRST), random.choice(LAST)
        name = f"{first} {last}"
        email = f"{first.lower()}.{last.lower()}{random.randint(1, 99)}@example.com"
        abn = ""
    else:
        word = random.choice(FACILITY_WORDS)
        name = {"AGED_CARE": f"{word} Aged Care", "HOSPITAL": f"{word} Private Hospital",
                "RESELLER": f"{word} Mobility Supplies"}[ctype]
        email = f"accounts@{word.lower().replace(' ', '')}{random.randint(1, 9)}.example.com.au"
        abn = gen_abn()
    return {"Company": company, "No": no, "Name": name, "Customer_Type": ctype, "ABN": abn, "Email": email,
            "Phone": f"04{random.randint(10000000, 99999999)}",
            "Address": f"{random.randint(1, 250)} {random.choice(STREETS)}", "City": city, "State": state,
            "Post_Code": pc, "Global_Dimension_1_Code": REGION_BY_CITY[city], "Customer_Posting_Group": posting,
            "Blocked": "", "SystemId": sid(), "SystemCreatedAt": ts(created), "SystemModifiedAt": ts(created)}


def build_customers():
    for company, cfg in COMPANIES.items():
        for i in range(1, cfg["cust"] + 1):
            created = cfg["start"] - dt.timedelta(days=random.randint(1, 400))
            data[company]["customer"].append(make_customer(company, f"C{i:05d}", created))
    # 25 Riverbend customers are the same real customers as CCG ones (same ABN or email), different No and name formatting
    ccg = data["CCG"]["customer"]
    rb = data["RIVERBEND"]["customer"]
    matched = random.sample(range(len(ccg)), 25)
    for k, idx in enumerate(matched):
        src = ccg[idx]
        tgt = rb[k * 4]
        tgt.update({"Name": src["Name"].upper() if k % 2 else src["Name"] + " ", "Customer_Type": src["Customer_Type"],
                    "ABN": src["ABN"], "Email": src["Email"].upper() if k % 3 == 0 else src["Email"],
                    "City": src["City"], "State": src["State"], "Post_Code": src["Post_Code"],
                    "Global_Dimension_1_Code": src["Global_Dimension_1_Code"],
                    "Customer_Posting_Group": src["Customer_Posting_Group"]})
    return matched


# ----------------------------------------------------------------- transactions
def price_lookup(company):
    return {i["No"]: i for i in data[company]["item"]}


def make_lines(company, doc_no, customer, location, created_iso, doc_kind):
    items = price_lookup(company)
    item_nos = list(items)
    lines = []
    wholesale = customer["Customer_Type"] in ("RESELLER", "AGED_CARE", "HOSPITAL")
    for ln in range(1, random.choices([1, 2, 3, 4], [45, 30, 15, 10])[0] + 1):
        it = items[random.choice(item_nos)]
        qty = random.randint(1, 8) if wholesale else random.choices([1, 2], [85, 15])[0]
        disc = random.choice([10, 12.5, 15, 20]) if wholesale else random.choice([0, 0, 0, 0, 5])
        price = float(it["Unit_Price"])
        amount = money(qty * price * (1 - disc / 100))
        vat = 0.10 if it["VAT_Prod_Posting_Group"] == "GST10" else 0.0
        row = {"Company": company, "Line_No": ln * 10000, "Type": "Item", "No": it["No"],
               "Description": it["Description"], "Location_Code": location, "Quantity": qty, "Unit_Price": price,
               "Line_Discount_Pct": disc, "Amount": amount, "Amount_Including_VAT": money(amount * (1 + vat)),
               "SystemId": sid(), "SystemCreatedAt": created_iso, "SystemModifiedAt": created_iso}
        if doc_kind == "order":
            row.update({"Document_Type": "Order", "Document_No": doc_no})
        else:
            row["Document_No"] = doc_no
        lines.append(row)
    return lines


def post_invoice(company, order, lines, posting_date, created_iso=None, record_truth=True):
    created_iso = created_iso or ts(posting_date)
    inv_no = next_no(company, "inv")
    hdr = {"Company": company, "No": inv_no, "Order_No": order["No"],
           "Sell_to_Customer_No": order["Sell_to_Customer_No"], "Order_Date": order["Order_Date"],
           "Posting_Date": posting_date.isoformat(), "Location_Code": order["Location_Code"],
           "Salesperson_Code": order["Salesperson_Code"],
           "Global_Dimension_1_Code": order["Global_Dimension_1_Code"],
           "Global_Dimension_2_Code": order["Global_Dimension_2_Code"],
           "SystemId": sid(), "SystemCreatedAt": created_iso, "SystemModifiedAt": created_iso}
    inv_lines = []
    for l in lines:
        il = {k: v for k, v in l.items() if k != "Document_Type"}
        il.update({"Document_No": inv_no, "SystemId": sid(), "SystemCreatedAt": created_iso,
                   "SystemModifiedAt": created_iso})
        inv_lines.append(il)
    ile = []
    for il in inv_lines:
        ile.append({"Company": company, "Entry_No": next_entry(company), "Item_No": il["No"],
                    "Posting_Date": posting_date.isoformat(), "Entry_Type": "Sale",
                    "Document_Type": "Sales Shipment", "Document_No": inv_no, "Location_Code": il["Location_Code"],
                    "Quantity": -int(il["Quantity"]), "SystemId": sid(), "SystemCreatedAt": created_iso,
                    "SystemModifiedAt": created_iso})
    if record_truth:
        truth_invoices.append((company, posting_date, sum(float(l["Amount"]) for l in inv_lines), inv_no))
    return hdr, inv_lines, ile


def make_credit_memo(company, inv_hdr, inv_lines, posting_date):
    created_iso = ts(posting_date)
    cm_no = next_no(company, "cm")
    src = random.choice(inv_lines)
    qty = random.randint(1, int(src["Quantity"]))
    amount = money(qty * float(src["Unit_Price"]) * (1 - float(src["Line_Discount_Pct"]) / 100))
    vat_ratio = float(src["Amount_Including_VAT"]) / float(src["Amount"]) if float(src["Amount"]) else 1
    hdr = {"Company": company, "No": cm_no, "Applies_to_Doc_No": inv_hdr["No"],
           "Sell_to_Customer_No": inv_hdr["Sell_to_Customer_No"], "Posting_Date": posting_date.isoformat(),
           "Return_Reason_Code": random.choice(["DAMAGED", "WRONG_SIZE", "NOT_SUITABLE", "FUNDING_DECLINED"]),
           "Location_Code": inv_hdr["Location_Code"], "Global_Dimension_1_Code": inv_hdr["Global_Dimension_1_Code"],
           "Global_Dimension_2_Code": inv_hdr["Global_Dimension_2_Code"],
           "SystemId": sid(), "SystemCreatedAt": created_iso, "SystemModifiedAt": created_iso}
    line = {"Company": company, "Document_No": cm_no, "Line_No": 10000, "Type": "Item", "No": src["No"],
            "Description": src["Description"], "Location_Code": src["Location_Code"], "Quantity": qty,
            "Unit_Price": src["Unit_Price"], "Line_Discount_Pct": src["Line_Discount_Pct"], "Amount": amount,
            "Amount_Including_VAT": money(amount * vat_ratio), "SystemId": sid(),
            "SystemCreatedAt": created_iso, "SystemModifiedAt": created_iso}
    ile = {"Company": company, "Entry_No": next_entry(company), "Item_No": src["No"],
           "Posting_Date": posting_date.isoformat(), "Entry_Type": "Sale", "Document_Type": "Sales Return Receipt",
           "Document_No": cm_no, "Location_Code": src["Location_Code"], "Quantity": qty, "SystemId": sid(),
           "SystemCreatedAt": created_iso, "SystemModifiedAt": created_iso}
    truth_cms.append((company, posting_date, amount, cm_no))
    return hdr, [line], ile


def stock_entries(company, d):
    """Purchases, transfers and adjustments for one day."""
    rows = []
    items = [i["No"] for i in data[company]["item"]]
    locs = [l[0] for l in LOCATIONS[company]]
    wh = [l[0] for l in LOCATIONS[company] if l[2] == "WAREHOUSE"][0]
    shows = [l for l in locs if l != wh]
    if d.weekday() == 0:  # weekly purchase receipts into the warehouse
        for it in random.sample(items, 12):
            rows.append(("Purchase", "Purchase Receipt", f"PR-{d:%y%m%d}", wh, it, random.randint(5, 30)))
    if d.weekday() in (1, 3):  # transfers warehouse -> showroom (two entries)
        for it in random.sample(items, 4):
            to = random.choice(shows)
            q = random.randint(1, 5)
            doc = f"TR-{d:%y%m%d}-{random.randint(100, 999)}"
            rows.append(("Transfer", "Transfer Shipment", doc, wh, it, -q))
            rows.append(("Transfer", "Transfer Receipt", doc, to, it, q))
    if random.random() < 0.15:
        it = random.choice(items)
        rows.append((random.choice(["Positive Adjmt.", "Negative Adjmt."]), "", f"ADJ-{d:%y%m%d}",
                     random.choice(locs), it, random.choice([-2, -1, 1, 2])))
    out = []
    for etype, dtype, doc, loc, it, q in rows:
        iso = ts(d)
        out.append({"Company": company, "Entry_No": next_entry(company), "Item_No": it,
                    "Posting_Date": d.isoformat(), "Entry_Type": etype, "Document_Type": dtype,
                    "Document_No": doc, "Location_Code": loc, "Quantity": q, "SystemId": sid(),
                    "SystemCreatedAt": iso, "SystemModifiedAt": iso})
    return out


def new_order(company, d, created_iso=None):
    cust = random.choice(data[company]["customer"])
    loc = random.choice([l[0] for l in LOCATIONS[company] if l[2] == "SHOWROOM"])
    created_iso = created_iso or ts(d)
    no = next_no(company, "ord")
    hdr = {"Company": company, "Document_Type": "Order", "No": no, "Sell_to_Customer_No": cust["No"],
           "Order_Date": d.isoformat(), "Location_Code": loc, "Status": "Released",
           "Salesperson_Code": random.choice(SALESPEOPLE), "Global_Dimension_1_Code": cust["Global_Dimension_1_Code"],
           "Global_Dimension_2_Code": BU_BY_TYPE[cust["Customer_Type"]],
           "SystemId": sid(), "SystemCreatedAt": created_iso, "SystemModifiedAt": created_iso}
    lines = make_lines(company, no, cust, loc, created_iso, "order")
    return hdr, lines


open_orders = {c: {} for c in COMPANIES}   # company -> order no -> (hdr, lines)
posted = {c: [] for c in COMPANIES}        # company -> list of (inv_hdr, inv_lines)


def build_history():
    cancelled_hist = 0
    for company, cfg in COMPANIES.items():
        pending_cm = []
        for d in daterange(cfg["start"], CUTOFF):
            data[company]["item_ledger_entry"].extend(stock_entries(company, d))
            weekend = d.weekday() >= 5
            n = max(0, int(random.gauss(cfg["orders_per_day"] * (0.3 if weekend else 1), 1.5)))
            for _ in range(n):
                hdr, lines = new_order(company, d)
                if random.random() < 0.02:
                    cancelled_hist += 1          # cancelled before posting: deleted, leaves no trace
                    continue
                backorder = random.random() < 0.01
                post_date = d + dt.timedelta(days=random.choices([0, 1, 2, 3, 5], [35, 30, 15, 12, 8])[0])
                if backorder or post_date > CUTOFF:
                    open_orders[company][hdr["No"]] = (hdr, lines)
                    continue
                ih, il, ile = post_invoice(company, hdr, lines, post_date)
                posted[company].append((ih, il))
                data[company]["sales_invoice_header"].append(ih)
                data[company]["sales_invoice_line"].extend(il)
                data[company]["item_ledger_entry"].extend(ile)
                if random.random() < 0.03:
                    cm_date = post_date + dt.timedelta(days=random.randint(2, 20))
                    pending_cm.append((cm_date, ih, il))
            for cm_date, ih, il in [p for p in pending_cm if p[0] == d]:
                ch, cl, cile = make_credit_memo(company, ih, il, cm_date)
                data[company]["sales_cr_memo_header"].append(ch)
                data[company]["sales_cr_memo_line"].extend(cl)
                data[company]["item_ledger_entry"].append(cile)
            pending_cm = [p for p in pending_cm if p[0] > d]
        for hdr, lines in open_orders[company].values():
            data[company]["sales_header"].append(hdr)
            data[company]["sales_line"].extend(lines)
    return cancelled_hist


# ----------------------------------------------------------------- incremental days
answer = {"traps": {}}


def incremental_day(d, day_index):
    batch = {c: defaultdict(list) for c in COMPANIES}
    for company in COMPANIES:
        b = batch[company]
        rate = 2 if company == "CCG" else 1

        # --- master data changes
        if day_index == 0:
            # SCD2: customers move region
            movers = random.sample(data[company]["customer"], 3 * rate)
            for c in movers:
                old = (c["City"], c["Global_Dimension_1_Code"])
                city, state, pc = random.choice([x for x in CITIES if REGION_BY_CITY[x[0]] != c["Global_Dimension_1_Code"]])
                c.update({"City": city, "State": state, "Post_Code": pc,
                          "Global_Dimension_1_Code": REGION_BY_CITY[city], "SystemModifiedAt": ts(d)})
                b["customer"].append(dict(c))
                answer["traps"].setdefault("scd2_region_changes", []).append(
                    {"company": company, "customer": c["No"], "from": old[1], "to": c["Global_Dimension_1_Code"]})
            # new customers
            start = len(data[company]["customer"])
            for i in range(2 * rate):
                nc = make_customer(company, f"C{start + i + 1:05d}", d)
                data[company]["customer"].append(nc)
                b["customer"].append(dict(nc))
        if day_index == 1:
            # price changes on items (affects price-at-time-of-sale)
            for it in random.sample(data[company]["item"], 2 * rate):
                old = it["Unit_Price"]
                it["Unit_Price"] = money(float(it["Unit_Price"]) * random.choice([1.05, 1.08, 0.9]))
                it["SystemModifiedAt"] = ts(d)
                b["item"].append(dict(it))
                answer["traps"].setdefault("price_changes", []).append(
                    {"company": company, "item": it["No"], "old": old, "new": it["Unit_Price"]})
        if day_index == 2 and company == "CCG":
            # data quality: a new customer with a blank name
            nc = make_customer(company, f"C{len(data[company]['customer']) + 1:05d}", d)
            nc["Name"] = ""
            data[company]["customer"].append(nc)
            b["customer"].append(dict(nc))
            answer["traps"]["blank_customer_name"] = nc["No"]

        # --- stock movements
        b["item_ledger_entry"].extend(stock_entries(company, d))

        # --- post some existing open orders (they leave the open-order key list, appear as invoices)
        opens = list(open_orders[company].items())
        to_post = random.sample(opens, min(len(opens), random.randint(3, 6) * rate))
        for no, (hdr, lines) in to_post:
            ih, il, ile = post_invoice(company, hdr, lines, d)
            posted[company].append((ih, il))
            b["sales_invoice_header"].append(ih)
            b["sales_invoice_line"].extend(il)
            b["item_ledger_entry"].extend(ile)
            del open_orders[company][no]

        # --- cancel (delete) open orders: they simply disappear
        opens = list(open_orders[company])
        for no in random.sample(opens, min(len(opens), 1 + (company == "CCG"))):
            del open_orders[company][no]
            answer["traps"].setdefault("deleted_open_orders", []).append({"company": company, "order": no})

        # --- modify an open order (quantity change)
        if open_orders[company]:
            no = random.choice(list(open_orders[company]))
            hdr, lines = open_orders[company][no]
            iso = ts(d)
            lines[0]["Quantity"] = int(lines[0]["Quantity"]) + 1
            lines[0]["Amount"] = money(lines[0]["Quantity"] * float(lines[0]["Unit_Price"]) * (1 - float(lines[0]["Line_Discount_Pct"]) / 100))
            vat = 0.1 if price_lookup(company)[lines[0]["No"]]["VAT_Prod_Posting_Group"] == "GST10" else 0
            lines[0]["Amount_Including_VAT"] = money(lines[0]["Amount"] * (1 + vat))
            lines[0]["SystemModifiedAt"] = iso
            hdr["SystemModifiedAt"] = iso
            b["sales_header"].append(dict(hdr))
            b["sales_line"].extend(dict(l) for l in lines)

        # --- today's new orders: most stay open, a few posted the same day
        for _ in range(COMPANIES[company]["orders_per_day"]):
            hdr, lines = new_order(company, d)
            if random.random() < 0.3:
                ih, il, ile = post_invoice(company, hdr, lines, d)
                posted[company].append((ih, il))
                b["sales_invoice_header"].append(ih)
                b["sales_invoice_line"].extend(il)
                b["item_ledger_entry"].extend(ile)
            else:
                open_orders[company][hdr["No"]] = (hdr, lines)
                b["sales_header"].append(dict(hdr))
                b["sales_line"].extend(dict(l) for l in lines)

        # --- credit memo on a recent invoice
        ih, il = random.choice(posted[company][-60:])
        ch, cl, cile = make_credit_memo(company, ih, il, d)
        b["sales_cr_memo_header"].append(ch)
        b["sales_cr_memo_line"].extend(cl)
        b["item_ledger_entry"].append(cile)

        # ------------------------------------------------- deliberate traps
        if day_index == 1 and company == "CCG":
            # late-arriving invoice: posting date 30 Sep, but created (and extracted) on 2 Oct
            hdr, lines = new_order(company, dt.date(2026, 9, 29), created_iso=ts(dt.date(2026, 9, 29)))
            ih, il, ile = post_invoice(company, hdr, lines, dt.date(2026, 9, 30), created_iso=ts(d, 9, 15))
            posted[company].append((ih, il))
            b["sales_invoice_header"].append(ih)
            b["sales_invoice_line"].extend(il)
            b["item_ledger_entry"].extend(ile)
            answer["traps"]["late_arriving_invoice"] = {"invoice": ih["No"], "posting_date": "2026-09-30",
                                                        "arrives_in": "incr_2026-10-02"}
            # API resend: duplicate rows of 3 invoice lines and 1 header in the same batch
            dup_lines = random.sample(b["sales_invoice_line"], 3)
            b["sales_invoice_line"].extend(dict(x) for x in dup_lines)
            dup_hdr = dict(random.choice(b["sales_invoice_header"]))
            b["sales_invoice_header"].append(dup_hdr)
            answer["traps"]["duplicate_rows"] = {
                "file": "incr_2026-10-02/sales_invoice_line.csv + sales_invoice_header.csv",
                "duplicate_invoice_lines": [f"{x['Document_No']}/{x['Line_No']}" for x in dup_lines],
                "duplicate_invoice_header": dup_hdr["No"]}
        if day_index == 2 and company == "CCG":
            # unknown item on a posted invoice line (item missing from Item table) - must NOT be dropped
            ih, il = posted[company][-1]
            bad = dict(il[0])
            bad.update({"Line_No": 990000, "No": "ITM-99999", "Description": "Discontinued item (legacy code)",
                        "Quantity": 1, "Unit_Price": 150.0, "Line_Discount_Pct": 0, "Amount": 150.0,
                        "Amount_Including_VAT": 150.0, "SystemId": sid()})
            il.append(bad)
            b["sales_invoice_line"].append(dict(bad))
            for t in truth_invoices:
                if t[3] == ih["No"]:
                    truth_invoices.remove(t)
                    truth_invoices.append((t[0], t[1], t[2] + 150.0, t[3]))
                    break
            answer["traps"]["unknown_item"] = {"invoice": ih["No"], "item": "ITM-99999", "amount": 150.0}
            # invalid open order line: blank quantity
            if b["sales_line"]:
                b["sales_line"][0]["Quantity"] = ""
                answer["traps"]["blank_quantity_order_line"] = (
                    f"{b['sales_line'][0]['Document_No']}/{b['sales_line'][0]['Line_No']}")

        # key snapshot of every open order right now (for delete detection)
        b["sales_header_keys"] = [{"Company": company, "Document_Type": "Order", "No": no}
                                  for no in sorted(open_orders[company])]
    return batch


# ----------------------------------------------------------------- run
def main():
    build_vendors()
    build_locations()
    build_items()
    matched = build_customers()
    cancelled_hist = build_history()

    # full extract (snapshot as at cutoff, before any incremental changes)
    full_dir = os.path.join(OUT, "bc_extract", "full_2026-09-30")
    snapshot = {t: [dict(r) for c in COMPANIES for r in data[c][t]] for t in COLS}
    for t, cols in COLS.items():
        write_csv(os.path.join(full_dir, f"{t}.csv"), snapshot[t], cols)

    for i, d in enumerate(INCR_DAYS):
        batch = incremental_day(d, i)
        folder = os.path.join(OUT, "bc_extract", f"incr_{d.isoformat()}")
        for t, cols in COLS.items():
            rows = [r for c in COMPANIES for r in batch[c].get(t, [])]
            cols_out = list(cols)
            if t == "sales_header" and i == 2:
                cols_out = cols + ["Delivery_Method"]          # schema drift on day 3
                for r in rows:
                    r["Delivery_Method"] = random.choice(["DELIVERY", "PICKUP", "INSTALL"])
            write_csv(os.path.join(folder, f"{t}.csv"), rows, cols_out)
        keys = [r for c in COMPANIES for r in batch[c]["sales_header_keys"]]
        write_csv(os.path.join(folder, "sales_header_keys.csv"), keys, KEYS_COLS)
    answer["traps"]["schema_drift"] = "incr_2026-10-03/sales_header.csv has a new column Delivery_Method"

    # control totals: what Business Central's own reports show (final truth, no duplicates)
    totals = defaultdict(lambda: {"inv": 0.0, "inv_count": 0, "cm": 0.0, "cm_count": 0})
    for company, d, amt, _ in truth_invoices:
        totals[(company, d)]["inv"] += amt
        totals[(company, d)]["inv_count"] += 1
    for company, d, amt, _ in truth_cms:
        totals[(company, d)]["cm"] += amt
        totals[(company, d)]["cm_count"] += 1
    rows = []
    for (company, d), v in sorted(totals.items()):
        rows.append({"Company": company, "Posting_Date": d.isoformat(), "Invoice_Count": v["inv_count"],
                     "Invoiced_Amount_Excl_GST": money(v["inv"]), "Credit_Memo_Count": v["cm_count"],
                     "Credited_Amount_Excl_GST": money(v["cm"]), "Net_Sales_Excl_GST": money(v["inv"] - v["cm"])})
    write_csv(os.path.join(OUT, "reference", "bc_control_totals.csv"), rows,
              ["Company", "Posting_Date", "Invoice_Count", "Invoiced_Amount_Excl_GST", "Credit_Memo_Count",
               "Credited_Amount_Excl_GST", "Net_Sales_Excl_GST"])

    # answer key
    answer["cross_company_customer_matches"] = 25
    answer["cross_company_item_matches_by_gtin"] = 40
    answer["open_orders_after_2026_10_03"] = {c: len(open_orders[c]) for c in COMPANIES}
    by_company = defaultdict(float)
    for company, d, amt, _ in truth_invoices:
        by_company[company] += amt
    cm_company = defaultdict(float)
    for company, d, amt, _ in truth_cms:
        cm_company[company] += amt
    answer["total_net_sales_excl_gst_to_2026_10_03"] = {c: money(by_company[c] - cm_company[c]) for c in COMPANIES}
    sep30 = {c: money(sum(a for co, d, a, _ in truth_invoices if co == c and d == dt.date(2026, 9, 30))) for c in COMPANIES}
    answer["sep_30_invoiced_excl_gst_final"] = sep30
    with open(os.path.join(OUT, "reference", "answer_key.json"), "w") as f:
        json.dump(answer, f, indent=2)
    print("done")


if __name__ == "__main__":
    main()
