"""Generate a small valid PDF fixture without external libraries (not user data)."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
stream=b'BT /F1 20 Tf 60 700 Td (Research Hub - Local PDF QA) Tj 0 -40 Td /F1 12 Tf (This is an isolated test fixture, not a research paper.) Tj ET'
objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
output=bytearray(b'%PDF-1.4\n');offsets=[0]
for i,obj in enumerate(objects,1):
    offsets.append(len(output));output.extend(str(i).encode()+b' 0 obj\n'+obj+b'\nendobj\n')
xref=len(output);output.extend(b'xref\n0 6\n0000000000 65535 f \n')
for offset in offsets[1:]:output.extend(f'{offset:010d} 00000 n \n'.encode())
output.extend(f'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
path=ROOT/'.artifacts/browser-qa.pdf';path.parent.mkdir(exist_ok=True);path.write_bytes(output)
print(path)
