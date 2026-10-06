#!/usr/bin/env bash
# Render a docx to PDF + contact sheets for visual QC, then run the XSD validator.
# Usage: render_check.sh <file.docx> [workdir]   (needs LibreOffice, poppler, pillow)
set -e
DOCX="$1"; W="${2:-render}"; SK=/mnt/skills/public/docx/scripts/office
mkdir -p "$W"; rm -f "$W"/pg-* "$W"/sheet*
python3 $SK/soffice.py --headless --convert-to pdf --outdir "$W" "$DOCX" >/dev/null 2>&1
PDF="$W/$(basename "${DOCX%.docx}").pdf"
pdfinfo "$PDF" | grep Pages
pdftoppm -jpeg -r 55 "$PDF" "$W/pg"
python3 -I - "$W" <<'PY'
import sys,glob
from PIL import Image
W=sys.argv[1]; fs=sorted(glob.glob(W+'/pg-*.jpg')); ims=[Image.open(f) for f in fs]; w,h=ims[0].size
for n in range(0,len(ims),6):
    M=Image.new('RGB',(w*3,h*2),'white')
    for j,im in enumerate(ims[n:n+6]): M.paste(im,((j%3)*w,(j//3)*h))
    M.save(f'{W}/sheet{n//6}.png')
print('contact sheets:',sorted(glob.glob(W+'/sheet*.png')))
PY
python3 $SK/validate.py "$DOCX" | tail -1
