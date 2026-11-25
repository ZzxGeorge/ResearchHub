"""Code-native waveform mark matching the existing Research Hub identity; PNG-in-ICO."""
import struct,zlib,math
from pathlib import Path
root=Path(__file__).resolve().parents[1];folder=root/'desktop/assets';folder.mkdir(parents=True,exist_ok=True)
size=256;points=[(48,130),(88,130),(108,65),(133,193),(155,113),(207,113)]
def distance(x,y,a,b):
    dx,dy=b[0]-a[0],b[1]-a[1];t=max(0,min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy)))
    return math.hypot(x-a[0]-t*dx,y-a[1]-t*dy)
raw=bytearray()
for y in range(size):
    raw.append(0)
    for x in range(size):
        corner=math.hypot(max(32-x,x-223,0),max(32-y,y-223,0))
        alpha=255 if corner<32 else 0
        white=min(distance(x,y,a,b) for a,b in zip(points,points[1:]))<6
        raw.extend((236,247,239,alpha) if white else (50,114,92,alpha))
def chunk(k,v):return struct.pack('>I',len(v))+k+v+struct.pack('>I',zlib.crc32(k+v)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',size,size,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')
(folder/'icon.png').write_bytes(png)
(folder/'icon.ico').write_bytes(struct.pack('<HHH',0,1,1)+struct.pack('<BBBBHHII',0,0,0,0,1,32,len(png),22)+png)
print(folder/'icon.ico')
