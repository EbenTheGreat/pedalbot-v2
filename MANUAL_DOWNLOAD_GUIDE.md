# Manual Download Guide for Testing

Due to network restrictions, please download these manuals manually from your browser.

## 📥 Download Instructions

### 1. Boss GT-1 Guitar Effects Processor

**Direct Download Link:**
```
https://static.roland.com/assets/media/pdf/GT-1_eng01_W.pdf
```

**Steps:**
1. Open the link above in your browser
2. Save the PDF as: `Boss_GT-1_Manual.pdf`
3. Move it to: `uploads_dir/Boss_GT-1_Manual.pdf`

**Alternative:** Visit https://boss.info/us/support/by_product/gt-1/owners_manuals/

---

### 2. Line 6 Helix Floor Multi-Effects

**Direct Download Link:**
```
https://line6.com/data/6/0a020a3f1a9b3f2c1b2f7f5d6/application/pdf/Helix%20Owner%27s%20Manual%20-%20English%20.pdf
```

**Steps:**
1. Open the link above in your browser
2. Save the PDF as: `Line6_Helix_Manual.pdf`
3. Move it to: `uploads_dir/Line6_Helix_Manual.pdf`

**Alternative:** Visit https://line6.com/support/manuals/helix

**Status:** ✅ Already downloaded (213 bytes - may need re-download if corrupted)

---

### 3. NUX MG-30 Multi-Effects Modeler

**Direct Download Link:**
```
https://www.nuxefx.com/asset/MG-30%20User%20Manual.pdf
```

**Steps:**
1. Open the link above in your browser
2. Save the PDF as: `NUX_MG-30_Manual.pdf`
3. Move it to: `uploads_dir/NUX_MG-30_Manual.pdf`

**Alternative Sources:**
- https://manuals.plus/nux/mg-30-versatile-modeler-manual
- https://www.scribd.com/document/[search for NUX MG-30]

---

## 🚀 Quick Test After Download

Once you have the PDFs downloaded, verify them:

```bash
# Check files are in place
ls -lh uploads_dir/*.pdf

# Verify they're real PDFs (should show file info)
file uploads_dir/*.pdf
```

Expected output:
```
Boss_GT-1_Manual.pdf: PDF document, version 1.X
Line6_Helix_Manual.pdf: PDF document, version 1.X
NUX_MG-30_Manual.pdf: PDF document, version 1.X
```

---

## 📝 Next Steps After Download

1. **Verify PDFs are valid** (not HTML error pages)
2. **Run the ingestion test:**
   ```bash
   uv run python -m backend.test.test_ingest_worker
   ```

3. **Monitor in Flower:** http://localhost:5555

---

## 💡 Alternative: Use Any Guitar Pedal Manual

If you have trouble downloading these specific manuals, you can use **ANY** guitar pedal/effects manual PDF you have. Common sources:

- **Boss Pedals:** https://boss.info/us/support/
- **Electro-Harmonix:** https://www.ehx.com/support/
- **TC Electronic:** https://www.tcelectronic.com/brand/tcelectronic/support
- **Strymon:** https://www.strymon.net/support/

Just make sure the PDF is:
- ✅ A real PDF file (not HTML)
- ✅ Contains actual manual content
- ✅ Is readable (not corrupted)
- ✅ Placed in `uploads_dir/` folder
