# GUI Consolidation Feature Guide

## Location of Consolidation Checkbox

The consolidation checkbox is located in the **Setup tab**, in the **Matching Settings** card:

```
┌─────────────────────────────────────────────────────────────┐
│  Matching Settings                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Similarity Threshold: [========|====] 80                   │
│  Recommended: 75-85. Higher = stricter matching             │
│                                                             │
│  ☐ Consolidate topics into columns (one row per URL-Segment)│  <-- CHECK THIS BOX
│  When enabled, multiple topics appear as Topic_1, Topic_2,  │
│  etc. in one row                                            │
│                                                             │
│  [ Run Matching ]  [ Reset Form ]                          │
└─────────────────────────────────────────────────────────────┘
```

## What Happens When Checked

### WITHOUT consolidation (default):
- Each topic gets its own row
- Output has columns: URL | Product | Domain | Segment | Topic
- Example: 636 rows for NL data

```
URL                     | Product    | Domain     | Segment          | Topic
https://example.com/... | Twinfield  | Accounting | Cash and banks   | Bank reconciliation
https://example.com/... | Twinfield  | Accounting | Cash and banks   | Banking module
https://example.com/... | Twinfield  | Accounting | Cash and banks   | Bank transactions
```

### WITH consolidation (checkbox checked):
- One row per URL+Segment combination
- Output has columns: URL | Product | Domain | Segment | Topic_1 | Topic_2 | Topic_3 | ...
- Example: 307 rows for NL data (51% reduction)

```
URL                     | Product    | Domain     | Segment        | Topic_1              | Topic_2         | Topic_3
https://example.com/... | Twinfield  | Accounting | Cash and banks | Bank reconciliation  | Banking module  | Bank transactions
```

## Steps to Use

1. Launch GUI: `launch_gui.bat`
2. Select country from dropdown (NL, SE, BE, GB)
3. File paths auto-populate (or select manually)
4. **✓ CHECK the "Consolidate topics into columns" checkbox**
5. Adjust similarity threshold if needed (default 80)
6. Click "Run Matching"
7. Output file will be in consolidated format!

## Important Notes

- **Segment names are NOT included as topics** - they appear in the Segment column only
- **Multiple segments**: If a URL matches different segments, it will appear in multiple rows (one per segment)
- **Output file name**: Same as before (e.g., `taxonomy_match_NL.xlsx`)
- **Backward compatible**: Unchecked = original one-row-per-topic format

## Troubleshooting

If the checkbox doesn't appear:
1. Make sure you're running the latest version of the code
2. Close and relaunch the GUI
3. Check for any error messages in the GUI

If rows aren't consolidating:
1. Verify the checkbox is checked before clicking "Run Matching"
2. Check the Console tab for the message: "Applying topic consolidation..."
3. Look for: "Consolidated to X rows with up to Y topics per row"
