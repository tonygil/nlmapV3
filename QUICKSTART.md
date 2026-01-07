# 🚀 Quick Start Guide

## Launch the Beautiful GUI

### Windows
```bash
python taxonomy_matcher_gui.py
```

### Alternative (if Python not in PATH)
```bash
py taxonomy_matcher_gui.py
```

---

## Step-by-Step Guide

### 1️⃣ Launch Application
Double-click `taxonomy_matcher_gui.py` or run from terminal

### 2️⃣ Setup Tab
- **Semantic File**: Click "Browse" → Select `semantic_carriers_list.xlsx`
- **Taxonomy File**: Click "Browse" → Select `NL Taxonomy V2.xlsx`
- **Output File**: Choose where to save results (default: `taxonomy_match.xlsx`)

### 3️⃣ Adjust Settings (Optional)
- Move slider to set **Similarity Threshold**
- Recommended: **80%** (balanced)
- Lower = more matches, Higher = stricter

### 4️⃣ Run Matching
- Click **"▶️ Run Matching"** button
- Watch progress in footer
- Switch to **Console tab** to see live logs

### 5️⃣ View Results
- Success message appears when done
- Open `taxonomy_match.xlsx` to see results
- Review in Excel or your preferred tool

---

## GUI Features

### 📋 Setup Tab
- File selection with browse dialogs
- Visual threshold slider
- One-click execution
- Reset button to start over

### 📊 Console Tab
- Real-time processing logs
- Colored output for readability
- Clear and Copy functions
- Full process transparency

### ℹ️ About Tab
- Application information
- Feature overview
- Version details

---

## What to Expect

### Processing
- ⏱️ **Time**: 30-60 seconds
- 📊 **Progress**: Live updates in footer
- 💚 **Success rate**: ~92% of URLs matched

### Results
- 📄 **Output file**: Excel format (.xlsx)
- 📈 **Rows**: ~350-450 (from 231 URLs)
- 🎯 **Columns**: URL | Product | Domain | Segment | Topic

---

## Tips for Best Results

### ✅ Do:
- Use recommended threshold (75-85%)
- Keep input files in project folder
- Check Console tab for detailed logs
- Review output in Excel

### ❌ Don't:
- Set threshold too high (>90%) - too strict
- Set threshold too low (<70%) - too many false matches
- Move/rename input files during processing
- Close app while processing

---

## Keyboard Shortcuts

| Action | Shortcut |
|--------|----------|
| Switch tabs | Ctrl+Tab |
| Copy log | Ctrl+C (in Console) |
| Close app | Alt+F4 |

---

## Troubleshooting Quick Fixes

### Issue: Files not found
**Fix**: Use Browse buttons to select files with full paths

### Issue: No matches found
**Fix**: Lower threshold to 75% and try again

### Issue: Too many matches
**Fix**: Raise threshold to 85% for stricter matching

### Issue: App freezes
**Fix**: Wait - processing may take up to 60 seconds

### Issue: GUI doesn't start
**Fix**: Install tkinter: `pip install tk`

---

## Example Workflow

```
1. Launch GUI → taxonomy_matcher_gui.py
2. Browse → semantic_carriers_list.xlsx
3. Browse → NL Taxonomy V2.xlsx
4. Set threshold → 80%
5. Click → Run Matching
6. Wait → ~45 seconds
7. Success → taxonomy_match.xlsx created
8. Open → View results in Excel
```

---

## Need More Help?

📖 **README.md** - Full documentation
📋 **USAGE.md** - Detailed instructions
⚙️ **CONFIG.md** - Advanced settings

---

**That's it! You're ready to match URLs to taxonomy topics!** 🎉
