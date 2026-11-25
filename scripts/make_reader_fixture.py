"""Three-page public test PDF: columns, vector/image content, searchable text and outline."""
from pathlib import Path
import struct
root=Path(__file__).resolve().parents[1]
objects=[b'<< /Type /Catalog /Pages 2 0 R /Outlines 8 0 R >>',b'<< /Type /Pages /Kids [3 0 R 4 0 R 5 0 R] /Count 3 >>']
for index in range(3):
 objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 6 0 R >> /XObject << /Im0 7 0 R >> >> /Contents {index+10} 0 R >>'.encode())
objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
image=bytes([30,110,80,220,240,220,170,210,190,50,100,160])
objects.append(b'<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Length 12 >>\nstream\n'+image+b'\nendstream')
objects.extend([b'<< /Type /Outlines /First 9 0 R /Last 9 0 R /Count 1 >>',b'<< /Title (Experiments) /Parent 8 0 R /Dest [4 0 R /Fit] >>'])
streams=[
 b'BT /F1 22 Tf 45 740 Td (Research Hub PDF acceptance) Tj /F1 12 Tf 0 -40 Td (Left column: posterior distribution.) Tj 285 0 Td (Right column: world models.) Tj -285 -28 Td (E[X] = sum x_i p_i) Tj 285 0 Td (d f / d x = J) Tj ET 0.2 0.5 0.4 RG 45 550 500 70 re S q 100 0 0 100 60 400 cm /Im0 Do Q',
 b'BT /F1 22 Tf 45 740 Td (Experiments) Tj /F1 14 Tf 0 -50 Td (The posterior is conditioned on observations.) Tj 0 -40 Td (Search, select and copy this sentence.) Tj ET',
 b'q 480 0 0 480 60 180 cm /Im0 Do Q'
]
for stream in streams:objects.append(b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream')
data=bytearray(b'%PDF-1.4\n');offsets=[0]
for i,value in enumerate(objects,1):offsets.append(len(data));data.extend(f'{i} 0 obj\n'.encode()+value+b'\nendobj\n')
xref=len(data);count=len(objects)+1;data.extend(f'xref\n0 {count}\n0000000000 65535 f \n'.encode())
for offset in offsets[1:]:data.extend(f'{offset:010d} 00000 n \n'.encode())
data.extend(f'trailer\n<< /Size {count} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
destination=root/'.artifacts/中文论文阅读验收.pdf';destination.parent.mkdir(exist_ok=True);destination.write_bytes(data);print(destination)
