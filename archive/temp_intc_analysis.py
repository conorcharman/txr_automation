import csv
from collections import Counter

def summarise_file(label, path):
    with open(path, encoding='utf-8-sig') as f:
        rows = list(csv.DictReader(f))
    rows = [r for r in rows if any(v.strip() for v in r.values())]
    print()
    print('=== ' + label + ' (' + str(len(rows)) + ' records) ===')

    inc_counts = Counter()
    qty_types = Counter()
    price_types = Counter()
    venues = Counter()
    ca_count = 0
    nore_count = 0
    times_with_7_30 = []
    times_without_7_30 = []

    for r in rows:
        txref = r.get('Transaction reference number') or r.get('Transaction Reference') or ''
        inc = r.get('INCIDENT_CODE', '')
        qt = r.get('Type of quantity', '')
        pt = r.get('Type of price', '')
        v = r.get('Venue', '')
        t = r.get('Trading date time_Time', '')
        ewf = r.get('Execution within firm', '')

        inc_counts[inc] += 1
        qty_types[qt] += 1
        price_types[pt] += 1
        venues[v] += 1

        if txref.startswith('CA'):
            ca_count += 1
        if ewf == 'NORE':
            nore_count += 1
        if '7_30' in inc:
            times_with_7_30.append(t)
        else:
            times_without_7_30.append(t)

    print('  CA-prefix records: ' + str(ca_count) + ' | NORE ewf: ' + str(nore_count))
    print('  Qty types: ' + str(dict(qty_types.most_common(5))))
    print('  Price types: ' + str(dict(price_types.most_common(5))))
    print('  Venues (top 5): ' + str(dict(venues.most_common(5))))
    if times_with_7_30:
        print('  Unique times WITH 7_30 (' + str(len(times_with_7_30)) + ' recs): ' + str(sorted(set(times_with_7_30))[:8]))
    if times_without_7_30:
        print('  Unique times WITHOUT 7_30 (' + str(len(times_without_7_30)) + ' recs): ' + str(sorted(set(times_without_7_30))[:8]))
    print('  Top incident combos:')
    for inc_code, cnt in inc_counts.most_common(8):
        print('    ' + str(cnt).rjust(5) + 'x  ' + (inc_code or '(empty)'))

files = [
    ('7_6 (current)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_6.csv'),
    ('7_6 (CM checked)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_6 - CM - Completed- Checked.csv'),
    ('7_6 (FY25Q3)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_6.csv'),
    ('7_28 (current)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_28.csv'),
    ('7_28 (CM checked)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_28 - CM Completed - Checked.csv'),
    ('7_28 (FY25Q3)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_28.csv'),
    ('7_30 (current raw)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_30.csv'),
    ('7_30 (JF checked)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_30 - JF Complete- Checked.csv'),
    ('7_30 (FY25Q3)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_30.csv'),
    ('7_38 (CM checked)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_38 - CM Completed - Checked.csv'),
    ('7_38 (FY25Q3)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_38.csv'),
    ('7_42 (CM checked)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_42 - CM Completed- Checked.csv'),
    ('7_42 (current raw)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_42.csv'),
    ('7_42 (FY25Q3)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_42.csv'),
    ('7_50 (CM checked)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_50 - CM Completed - Checked.csv'),
    ('7_50 (FY25Q3)', r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_50.csv'),
]

for label, path in files:
    try:
        summarise_file(label, path)
    except Exception as e:
        print('ERROR ' + label + ': ' + str(e))

import sys; sys.exit(0)

_OLD_FILES = {
    '7_6 (current)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_6.csv',
    '7_6 (CM checked)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_6 - CM - Completed- Checked.csv',
    '7_6 (FY25Q3)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_6.csv',
    '7_28 (current)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_28.csv',
    '7_28 (CM checked)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_28 - CM Completed - Checked.csv',
    '7_28 (FY25Q3)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_28.csv',
    '7_30 (current raw)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_30.csv',
    '7_30 (JF checked)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_30 - JF Complete- Checked.csv',
    '7_30 (FY25Q3)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_30.csv',
    '7_38 (CM checked)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_38 - CM Completed - Checked.csv',
    '7_38 (FY25Q3)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_38.csv',
    '7_42 (CM checked)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_42 - CM Completed- Checked.csv',
    '7_42 (current raw)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_42.csv',
    '7_42 (FY25Q3)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_42.csv',
    '7_50 (CM checked)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\7_50 - CM Completed - Checked.csv',
    '7_50 (FY25Q3)': r'C:\Users\ccharm\Desktop\Data\txr_automated_accuracy_testing\accuracy_testing\2026\INTC_ISIN\FY25 Q3 - 7_50.csv',
}

for label, path in files.items():
    try:
        with open(path, encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        rows = [r for r in rows if any(v.strip() for v in r.values())]
        print()
        print('=== ' + label + ' (' + str(len(rows)) + ' records) ===')
        for r in rows:
            txref = (r.get('Transaction reference number') or r.get('Transaction Reference') or '')[:22]
            date = r.get('Trading date time_Date', '')
            time_ = r.get('Trading date time_Time', '')
            us = r.get('Trading date time_Microseconds', '')
            qty_type = r.get('Type of quantity', '')
            price_type = r.get('Type of price', '')
            qty = r.get('Quantity', '')
            netamt = r.get('Net amount', '')
            venue = r.get('Venue', '')
            ewf = (r.get('Execution within firm') or '')[:12]
            ewf_type = r.get('Type of execution within firm', '')
            inc = r.get('INCIDENT_CODE', '')
            err = r.get('Error (Y/N)', '')
            corr = (r.get('Correction') or '')[:15]
            cmt = (r.get('Comments') or '')[:40]
            isin = r.get('Instrument identification code', '')
            # 7_6 specific columns
            parent_ref = (r.get('parent_ref') or '')[:15]
            bulk_ref_col = (r.get('bulk_ref') or '')[:12]
            parent_qty = r.get('parent_qty', '')
            net_qty = r.get('net_qty', '')
            diff = r.get('difference', '')
            line = ('  ref=' + txref + ' date=' + date + ' time=' + time_ +
                    ' us=' + us + ' qty_t=' + qty_type + ' pr_t=' + price_type +
                    ' qty=' + qty + ' net=' + netamt + ' venue=' + venue +
                    ' ewf=' + ewf + ' ewft=' + ewf_type + ' isin=' + isin[:12] +
                    ' err=' + err + ' corr=' + corr + ' cmt=' + cmt)
            if parent_ref:
                line += ' parent=' + parent_ref + ' bulk=' + bulk_ref_col + ' p_qty=' + parent_qty + ' n_qty=' + net_qty + ' diff=' + diff
            print(line)
            if inc:
                print('       inc=' + inc)
    except Exception as e:
        print('=== ' + label + ' ERROR: ' + str(e) + ' ===')
