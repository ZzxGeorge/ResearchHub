// @vitest-environment node
import {describe,it,expect} from 'vitest';
import {getDocument} from 'pdfjs-dist';
import {pdfRect} from '../src/reading';

function publicPdf(){
 const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << >> /Contents 4 0 R >>','<< /Length 0 >>\nstream\n\nendstream'];
 let data='%PDF-1.4\n';const offsets=[0];for(let i=0;i<objects.length;i++){offsets.push(data.length);data+=`${i+1} 0 obj\n${objects[i]}\nendobj\n`;}
 const xref=data.length;data+=`xref\n0 5\n0000000000 65535 f \n`;for(const offset of offsets.slice(1))data+=String(offset).padStart(10,'0')+' 00000 n \n';data+=`trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;return new TextEncoder().encode(data);
}

describe('official PDF.js viewport coordinates',()=>{
 it('keeps a multi-line source reversible at every rotation, zoom and CSS split width',async()=>{
  const doc=await getDocument({data:publicPdf(),isEvalSupported:false}).promise;
  try{const page=await doc.getPage(1);const originals=[[72,600,180,614],[72,580,240,594]];
   for(const rotation of [0,90,180,270])for(const scale of [.37,.75,1,1.5,3])for(const cssWidth of [240,440,800]){
    const viewport=page.getViewport({scale,rotation}),ratio=cssWidth/viewport.width;
    for(const original of originals){const screen=pdfRect(viewport.convertToViewportRectangle(original)).map(v=>v*ratio);const a=viewport.convertToPdfPoint(screen[0]/ratio,screen[1]/ratio),b=viewport.convertToPdfPoint(screen[2]/ratio,screen[3]/ratio),restored=pdfRect([...a,...b]);restored.forEach((n,i)=>expect(n).toBeCloseTo(original[i],7));}
   }
  }finally{await doc.destroy();}
 });
});
