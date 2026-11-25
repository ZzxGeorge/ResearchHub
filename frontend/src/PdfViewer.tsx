import {useEffect,useRef,useState} from 'react';
import {ChevronLeft,ChevronRight,Download,Maximize,Minus,Plus,Search,Sidebar} from 'lucide-react';
import type {PDFDocumentProxy} from 'pdfjs-dist';
import type {PDFViewer as Viewer} from 'pdfjs-dist/types/web/pdf_viewer';
import type {EventBus as Bus} from 'pdfjs-dist/types/web/event_utils';
import type {PDFLinkService as Links} from 'pdfjs-dist/types/web/pdf_link_service';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';
import {api} from './api';
type Position={page:number;scale:string;offset:number};
type Outline={title:string;dest:any;items:Outline[]};
function Thumbnail({doc,page,onClick}:{doc:PDFDocumentProxy;page:number;onClick:()=>void}){
 const canvas=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{let live=true;let task:any;const observer=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting)return;observer.disconnect();void(async()=>{try{const p=await doc.getPage(page);if(!live||!canvas.current)return;const viewport=p.getViewport({scale:110/p.getViewport({scale:1}).width});canvas.current.width=viewport.width;canvas.current.height=viewport.height;task=p.render({canvasContext:canvas.current.getContext('2d')!,viewport});await task.promise;}catch{}})();});if(canvas.current)observer.observe(canvas.current);return()=>{live=false;task?.cancel();observer.disconnect();};},[doc,page]);
 return <button className="pdf-thumbnail" onClick={onClick} title={'跳转到第 '+page+' 页'}><canvas ref={canvas}/><span>{page}</span></button>;
}
/** Reuses PDF.js and its official lazy continuous viewer; no document scripts are enabled. */
export function PdfViewer({url}:{url:string}){
 const root=useRef<HTMLElement>(null),container=useRef<HTMLDivElement>(null),viewerElement=useRef<HTMLDivElement>(null);
 const viewer=useRef<Viewer|null>(null),bus=useRef<Bus|null>(null),links=useRef<Links|null>(null),position=useRef<Position>({page:1,scale:'page-width',offset:0});
 const [doc,setDoc]=useState<PDFDocumentProxy|null>(null),[page,setPage]=useState(1),[scale,setScale]=useState('page-width'),[zoom,setZoom]=useState(1),[error,setError]=useState(''),[loading,setLoading]=useState(true),[side,setSide]=useState(''),[outline,setOutline]=useState<Outline[]>([]),[query,setQuery]=useState(''),[matches,setMatches]=useState(''),[saveError,setSaveError]=useState(''),[expanded,setExpanded]=useState(false);
 useEffect(()=>{
  let live=true,initialized=false,timer:ReturnType<typeof setTimeout>|undefined,task:any,pdf:PDFDocumentProxy|undefined,observer:ResizeObserver|undefined;
  const abort=new AbortController();
  let pending=Promise.resolve();
  function persist(final=false){if(!initialized)return;const value={...position.current};const send=()=>api(url.replace('/api','')+'/reading-state',{method:'PUT',body:JSON.stringify(value),keepalive:final}).then(()=>{if(live)setSaveError('');}).catch(()=>{if(live)setSaveError('阅读位置尚未保存，请检查服务连接。');});pending=pending.then(send);}
  setLoading(true);setError('');setDoc(null);setOutline([]);
  void(async()=>{try{
   const pdfjs=await import('pdfjs-dist');(globalThis as any).pdfjsLib=pdfjs;
   const {PDFViewer,EventBus,PDFLinkService,PDFFindController}=await import('pdfjs-dist/web/pdf_viewer.mjs');
   if(!live||!container.current||!viewerElement.current)return;
   pdfjs.GlobalWorkerOptions.workerSrc=workerUrl;
   const events=new EventBus(),link=new PDFLinkService({eventBus:events,externalLinkTarget:2}),find=new PDFFindController({eventBus:events,linkService:link});
   const l10n={getLanguage:()=> 'zh-CN',getDirection:()=> 'ltr',get:async(_key:string,_args:any,fallback:string)=>fallback||'',translate:async()=>{},pause:()=>{},resume:()=>{}};
   const instance=new PDFViewer({container:container.current,viewer:viewerElement.current,eventBus:events,linkService:link,findController:find,textLayerMode:1,annotationMode:0,l10n:l10n as any,maxCanvasPixels:16777216,abortSignal:abort.signal});
   viewer.current=instance;bus.current=events;links.current=link;link.setViewer(instance);
   const saved:Position=await api(url.replace('/api','')+'/reading-state');if(!live)return;position.current=saved;
   events.on('pagesinit',()=>{if(!live)return;instance.currentScaleValue=saved.scale;instance.currentPageNumber=Math.min(saved.page,pdf!.numPages);setPage(instance.currentPageNumber);setScale(saved.scale);requestAnimationFrame(()=>requestAnimationFrame(()=>{if(!live)return;const p=instance.getPageView(instance.currentPageNumber-1);if(p&&container.current)container.current.scrollTop=p.div.offsetTop+saved.offset*p.div.clientHeight;initialized=true;}));});
   events.on('pagerendered',(e:any)=>{if(live){setLoading(false);if(e.error)setError('PDF 页面无法渲染：'+e.error.message);}});
   events.on('pagechanging',(e:any)=>{if(live)setPage(e.pageNumber);});
   events.on('scalechanging',(e:any)=>{if(live){setZoom(e.scale);setScale(instance.currentScaleValue);}});
   events.on('updateviewarea',()=>{if(!live||!initialized||!container.current)return;const p=instance.getPageView(instance.currentPageNumber-1);position.current={page:instance.currentPageNumber,scale:instance.currentScaleValue,offset:p?Math.min(1,Math.max(0,(container.current.scrollTop-p.div.offsetTop)/p.div.clientHeight)):0};clearTimeout(timer);timer=setTimeout(()=>persist(),650);});
   const counts=(e:any)=>{if(live)setMatches(e.matchesCount?.total?`${e.matchesCount.current} / ${e.matchesCount.total}`:'无匹配');};
   events.on('updatefindmatchescount',counts);events.on('updatefindcontrolstate',counts);
   task=pdfjs.getDocument({url,cMapUrl:'/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/pdfjs/standard_fonts/',useSystemFonts:true,isEvalSupported:false});
   pdf=await task.promise;if(!live)return;setDoc(pdf!);link.setDocument(pdf!);find.setDocument(pdf!);instance.setDocument(pdf!);
   const items=await pdf!.getOutline();if(live)setOutline(items||[]);
   observer=new ResizeObserver(()=>{if(['page-width','page-fit'].includes(instance.currentScaleValue))instance.currentScaleValue=instance.currentScaleValue;});observer.observe(container.current);
  }catch(e){if(live){setError('PDF 无法打开：'+String(e));setLoading(false);}}})();
  const flush=()=>persist(true);window.addEventListener('pagehide',flush);
  return()=>{clearTimeout(timer);persist(true);live=false;abort.abort();observer?.disconnect();window.removeEventListener('pagehide',flush);viewer.current?.setDocument(null as any);viewer.current=null;links.current=null;bus.current=null;void task?.destroy();};
 },[url]);
 useEffect(()=>{const escape=(event:KeyboardEvent)=>{if(event.key==='Escape')setExpanded(false);};window.addEventListener('keydown',escape);return()=>window.removeEventListener('keydown',escape);},[]);
 function go(value:number){if(viewer.current&&doc)viewer.current.currentPageNumber=Math.min(doc.numPages,Math.max(1,value));}
 function resize(value:string){if(viewer.current)viewer.current.currentScaleValue=value;}
 function search(value:string,type='',previous=false){setQuery(value);if(!value)setMatches('');bus.current?.dispatch('find',{source:root.current,type,query:value,phraseSearch:true,caseSensitive:false,entireWord:false,highlightAll:true,findPrevious:previous,matchDiacritics:false});}
 function outlineItems(items:Outline[],depth=0):React.ReactNode{return items.map((item,i)=><div key={depth+'-'+i}><button className="pdf-outline-item" style={{paddingLeft:10+depth*12}} onClick={()=>void links.current?.goToDestination(item.dest)}>{item.title}</button>{outlineItems(item.items||[],depth+1)}</div>);}
 return <section ref={root} className={'pdf-reader '+(expanded?'reader-expanded':'')} aria-label="论文 PDF 阅读器"><div className="pdf-reader-toolbar">
 <button className="icon-button" title="页面缩略图" onClick={()=>setSide(side==='thumbnails'?'':'thumbnails')}><Sidebar size={17}/></button><button className="ghost" onClick={()=>setSide(side==='outline'?'':'outline')}>目录</button>
 <button className="icon-button" title="PDF 上一页" disabled={page<=1} onClick={()=>go(page-1)}><ChevronLeft size={16}/></button><input aria-label="PDF 页码" type="number" min={1} max={doc?.numPages||1} value={page} onChange={e=>go(Number(e.target.value)||1)}/><span>/ {doc?.numPages||'…'}</span><button className="icon-button" title="PDF 下一页" disabled={!doc||page>=doc.numPages} onClick={()=>go(page+1)}><ChevronRight size={16}/></button>
 <button className="icon-button" title="缩小 PDF" onClick={()=>resize(String(Math.max(.25,zoom-.25)))}><Minus size={15}/></button><select aria-label="PDF 缩放模式" value={['page-width','page-fit'].includes(scale)?scale:'custom'} onChange={e=>resize(e.target.value)}><option value="page-width">适应宽度</option><option value="page-fit">适应整页</option><option value="custom" disabled>{Math.round(zoom*100)}%</option>{[.5,1,1.5,2,3].map(n=><option key={n} value={n}>{n*100}%</option>)}</select><button className="icon-button" title="放大 PDF" onClick={()=>resize(String(Math.min(5,zoom+.25)))}><Plus size={15}/></button>
 <button className="icon-button" title="全屏阅读" onClick={()=>{if(expanded){setExpanded(false);return;}if(window.document.fullscreenElement)void window.document.exitFullscreen();else void root.current?.requestFullscreen().catch(()=>setExpanded(true));}}><Maximize size={16}/></button><a href={url} className="icon-button" title="打开原始 PDF" target="_blank" rel="noreferrer"><Download size={15}/></a></div>
 <div className="pdf-search"><Search size={15}/><input aria-label="搜索 PDF 文本" placeholder="搜索论文文本（扫描件需 OCR）" value={query} onChange={e=>search(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')search(query,'again',e.shiftKey);}}/><span>{matches}</span><button className="icon-button" title="上一个搜索结果" onClick={()=>search(query,'again',true)}><ChevronLeft size={15}/></button><button className="icon-button" title="下一个搜索结果" onClick={()=>search(query,'again')}><ChevronRight size={15}/></button></div>
 {saveError&&<div className="pdf-warning">{saveError}</div>}<div className="pdf-reader-body">{side&&<aside className="pdf-reader-sidebar">{side==='outline'?(outline.length?outlineItems(outline):<p>此 PDF 没有内置目录。</p>):doc&&Array.from({length:doc.numPages},(_,i)=><Thumbnail key={i} doc={doc} page={i+1} onClick={()=>go(i+1)}/>)}</aside>}<div className="pdf-view-shell"><div ref={container} className="pdf-scroll-container"><div ref={viewerElement} className="pdfViewer"/></div>{loading&&!error&&<div className="pdf-loading">正在渲染本地 PDF…</div>}{error&&<p className="notice error pdf-error" role="alert">{error}</p>}</div></div></section>;
}
