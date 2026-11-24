import {cpSync,mkdirSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
for(const folder of ['cmaps','standard_fonts']){
 const destination=new URL(`../public/pdfjs/${folder}`,import.meta.url);
 mkdirSync(fileURLToPath(destination),{recursive:true});
 cpSync(new URL(`../node_modules/pdfjs-dist/${folder}`,import.meta.url),destination,{recursive:true});
}
