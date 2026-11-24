import {useEffect,useRef,useState} from 'react';
import {ChevronLeft,ChevronRight,Download,Minus,Plus} from 'lucide-react';
import type {PDFDocumentProxy,RenderTask} from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

export function PdfViewer({url}:{url:string}){
 const canvas=useRef<HTMLCanvasElement>(null),container=useRef<HTMLDivElement>(null),document=useRef<PDFDocumentProxy|null>(null),renderTask=useRef<RenderTask|null>(null);
 const [pages,setPages]=useState(0),[page,setPage]=useState(1),[zoom,setZoom]=useState(1),[error,setError]=useState(''),[loading,setLoading]=useState(true),[width,setWidth]=useState(400);
 useEffect(()=>{let live=true;let task:{destroy:()=>Promise<void>}|undefined;setError('');setLoading(true);setPages(0);setPage(1);
  void (async()=>{try{const pdfjs=await import('pdfjs-dist');if(!live)return;pdfjs.GlobalWorkerOptions.workerSrc=workerUrl;const loadingTask=pdfjs.getDocument({url,cMapUrl:'/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/pdfjs/standard_fonts/',useSystemFonts:true,isEvalSupported:false});task=loadingTask;const loaded=await loadingTask.promise;if(!live){await loaded.destroy();return;}document.current=loaded;setPages(loaded.numPages);}catch(e){if(live){setError('PDF 无法打开：'+String(e));setLoading(false);}}})();
  return()=>{live=false;renderTask.current?.cancel();document.current=null;void task?.destroy();};
 },[url]);
 useEffect(()=>{if(!container.current)return;const observer=new ResizeObserver(entries=>setWidth(Math.max(180,entries[0].contentRect.width-26)));observer.observe(container.current);return()=>observer.disconnect();},[]);
 useEffect(()=>{let live=true;let current:RenderTask|undefined;
  if(!pages||!document.current)return;
  setLoading(true);setError('');
  void(async()=>{try{renderTask.current?.cancel();const pdfPage=await document.current!.getPage(page);if(!live||!canvas.current)return;const natural=pdfPage.getViewport({scale:1});const viewport=pdfPage.getViewport({scale:width/natural.width*zoom});const ratio=Math.min(window.devicePixelRatio||1,2);const element=canvas.current;element.width=viewport.width*ratio;element.height=viewport.height*ratio;element.style.width=viewport.width+'px';element.style.height=viewport.height+'px';const context=element.getContext('2d');if(!context)throw new Error('Canvas unavailable');current=pdfPage.render({canvasContext:context,viewport,transform:[ratio,0,0,ratio,0,0]});renderTask.current=current;await current.promise;}catch(e){if(live&&!(e instanceof Error&&e.name==='RenderingCancelledException'))setError('页面渲染失败：'+String(e));}finally{if(live)setLoading(false);}})();
  return()=>{live=false;current?.cancel();};
 },[page,pages,zoom,width]);
 return <section className="pdf-viewer" aria-label="论文 PDF 阅读器"><div className="pdf-toolbar"><button className="icon-button" title="PDF 上一页" disabled={page<=1} onClick={()=>setPage(page-1)}><ChevronLeft size={16}/></button><input aria-label="PDF 页码" type="number" min={1} max={pages||1} value={page} onChange={e=>setPage(Math.max(1,Math.min(pages||1,Number(e.target.value)||1)))}/><span>/ {pages||'…'}</span><button className="icon-button" title="PDF 下一页" disabled={page>=pages} onClick={()=>setPage(page+1)}><ChevronRight size={16}/></button><button className="icon-button" title="缩小 PDF" disabled={zoom<=0.5} onClick={()=>setZoom(Math.max(0.5,zoom-0.25))}><Minus size={15}/></button><span>{Math.round(zoom*100)}%</span><button className="icon-button" title="放大 PDF" disabled={zoom>=3} onClick={()=>setZoom(Math.min(3,zoom+0.25))}><Plus size={15}/></button><a href={url} className="icon-button" title="打开原始 PDF" target="_blank" rel="noreferrer"><Download size={15}/></a></div><div ref={container} className="pdf-pages">{loading&&<div className="pdf-loading">正在渲染本地 PDF…</div>}{error?<p className="notice error">{error}</p>:<canvas ref={canvas} aria-label={'PDF 第 '+page+' 页'}/>}</div></section>;
}
