# FORM motion library

FORM combines two kinds of attributed motion references. They are planning and
preview inputs, not training examples for an automatic dance classifier.

The bundled sample clips are derived from the **AIST++ Dance Motion Dataset**
annotations published by Google LLC under CC BY 4.0:
https://google.github.io/aistplusplus_dataset/

FORM converts SMPL axis-angle annotations to an original generic skeleton for
preview and planning. It does not redistribute the separately licensed SMPL
body model or the source dance videos. AIST Dance Video Database media has
separate terms of use.

Regenerate the local sample library from an authorized AIST++ `motions/`
directory:

```powershell
.\.venv\Scripts\python.exe scripts\import_aistpp.py `
  data\aistpp\source\motions backend\motion_library\aistpp
```

## Curated Bharatanatyam adavu references

The `adavu/` collection contains five compact full-body landmark sequences
derived from publicly linked class demonstrations: Thattadavu, Nattadavu,
Ta Tei Tei Ta / Paraval, Kudithu Mettu, and Tha Hatha Jham / Theermaana.
Each catalog entry preserves its source URL, teacher/channel attribution,
style label, and extraction timestamp.

These names are curator-supplied family labels. FORM can select and animate a
named family, but it does not claim to recognize an unknown video's adavu.
The original videos remain outside the application in the ignored
`data/adavus/raw/` directory; only derived landmarks are bundled.

To rebuild the collection after placing the five source videos locally:

```powershell
.\.venv\Scripts\python.exe scripts\import_adavu_references.py
```

The source manifest is `scripts/adavu_sources.json`.
