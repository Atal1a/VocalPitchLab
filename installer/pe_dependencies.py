"""Read PE imports without loading DLLs or requiring a packaging dependency."""
import struct
from pathlib import Path

def imports(path):
    b=Path(path).read_bytes()
    if b[:2]!=b'MZ':return set()
    pe=struct.unpack_from('<I',b,60)[0]
    if b[pe:pe+4]!=b'PE\0\0':return set()
    n=struct.unpack_from('<H',b,pe+6)[0];opt_size=struct.unpack_from('<H',b,pe+20)[0];opt=pe+24
    magic=struct.unpack_from('<H',b,opt)[0]
    if magic not in (267,523):raise ValueError(f'Unknown PE optional header: {path}')
    dd=opt+(112 if magic==523 else 96)
    image_base=struct.unpack_from('<Q' if magic==523 else '<I',b,opt+(24 if magic==523 else 28))[0]
    sections=[]
    for i in range(n):
        o=opt+opt_size+40*i;vs,va,raw,ptr=struct.unpack_from('<IIII',b,o+8);sections.append((va,max(vs,raw),ptr))
    def offset(rva):
        for va,size,ptr in sections:
            if va<=rva<va+size:return ptr+rva-va
        if rva<len(b):return rva
        raise ValueError(f'Unmapped RVA {rva}: {path}')
    def string(rva):
        o=offset(rva);return b[o:b.index(b'\0',o)].decode('ascii').lower()
    result=set()
    for index,stride,namepos in ((1,20,12),(13,32,4)):
        rva,size=struct.unpack_from('<II',b,dd+8*index)
        if not rva:continue
        o=offset(rva)
        for pos in range(o,min(o+size,len(b)),stride):
            row=b[pos:pos+stride]
            if not any(row):break
            name=struct.unpack_from('<I',row,namepos)[0]
            if index==13 and not struct.unpack_from('<I',row,0)[0]&1:name-=image_base
            if name:result.add(string(name))
    return result
