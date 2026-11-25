import {useEffect,useRef,useState} from 'react';
import {ChevronLeft,ChevronRight,Download,Maximize,Minus,Plus,Search,Sidebar} from 'lucide-react';
import type {PDFDocumentProxy} from 'pdfjs-dist';
import type {PDFViewer as Viewer} from 'pdfjs-dist/types/web/pdf_viewer';
import type {EventBus as Bus} from 'pdfjs-dist/types/web/event_utils';
import type {PDFLinkService as Links} from 'pdfjs-dist/types/web/pdf_link_service';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import 'pdfjs-dist/web/pdf_viewer.css';
import {api} from './api';
import {cleanSelection,pdfRect,type SelectionSource,type Source,type CaptureAction} from './reading';
type Position={page:number;scale:string;offset:number;rotation?:number};
type Outline={title:string;dest:any;items:Outline[]};
function Thumbnail({doc,page,onClick}:{doc:PDFDocumentProxy;page:number;onClick:()=>void}){
 const canvas=useRef<HTMLCanvasElement>(null);
 useEffect(()=>{let live=true;let task:any;const observer=new IntersectionObserver(entries=>{if(!entries[0].isIntersecting)return;observer.disconnect();void(async()=>{try{const p=await doc.getPage(page);if(!live||!canvas.current)return;const viewport=p.getViewport({scale:110/p.getViewport({scale:1}).width});canvas.current.width=viewport.width;canvas.current.height=viewport.height;task=p.render({canvasContext:canvas.current.getContext('2d')!,viewport});await task.promise;}catch{}})();});if(canvas.current)observer.observe(canvas.current);return()=>{live=false;task?.cancel();observer.disconnect();};},[doc,page]);
 return <button className="pdf-thumbnail" onClick={onClick} title={'跳转到第 '+page+' 页'}><canvas ref={canvas}/><span>{page}</span></button>;
}
/** Reuses PDF.js and its official lazy continuous viewer; no document scripts are enabled. */
export function PdfViewer({url,paperId='',sha256='',sources=[],focusSource,onCapture,onSelectSource,onError=()=>{}}:{url:string;paperId?:string;sha256?:string;sources?:Source[];focusSource?:Source|null;onCapture?:(s:SelectionSource,a:CaptureAction)=>void;onSelectSource?:(s:Source)=>void;onError?:(e:unknown)=>void}){
 const root=useRef<HTMLElement>(null),container=useRef<HTMLDivElement>(null),viewerElement=useRef<HTMLDivElement>(null);
 const viewer=useRef<Viewer|null>(null),bus=useRef<Bus|null>(null),links=useRef<Links|null>(null),position=useRef<Position>({page:1,scale:'page-width',offset:0});
 const [doc,setDoc]=useState<PDFDocumentProxy|null>(null),[page,setPage]=useState(1),[scale,setScale]=useState('page-width'),[zoom,setZoom]=useState(1),[error,setError]=useState(''),[loading,setLoading]=useState(true),[side,setSide]=useState(''),[outline,setOutline]=useState<Outline[]>([]),[query,setQuery]=useState(''),[matches,setMatches]=useState(''),[saveError,setSaveError]=useState(''),[expanded,setExpanded]=useState(false);
 const [selection,setSelection]=useState<{source:SelectionSource;x:number;y:number}|null>(null),[more,setMore]=useState(false),[scanHint,setScanHint]=useState('');
 const sourceRef=useRef(sources),focusRef=useRef(focusSource),selectRef=useRef(onSelectSource),drawRef=useRef<()=>void>(()=>{}),jumpRef=useRef<()=>void>(()=>{}),focusTimer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),textCache=useRef(new Map<number,Promise<string>>());
 const focusUntil=useRef(0);
 sourceRef.current=sources;focusRef.current=focusSource;selectRef.current=onSelectSource;
 useEffect(()=>{let raf=0;const schedule=()=>{cancelAnimationFrame(raf);raf=requestAnimationFrame(()=>drawRef.current());};schedule();const observer=new ResizeObserver(schedule);if(viewerElement.current)observer.observe(viewerElement.current);return()=>{observer.disconnect();cancelAnimationFrame(raf);};},[sources,focusSource]);
 useEffect(()=>{jumpRef.current();},[focusSource,doc]);
 useEffect(()=>{
  let live=true,initialized=false,timer:ReturnType<typeof setTimeout>|undefined,task:any,pdf:PDFDocumentProxy|undefined,observer:ResizeObserver|undefined;
  const abort=new AbortController();
  let pending=Promise.resolve();
  function persist(final=false){if(!initialized)return;const value={...position.current};const send=()=>api(url.replace('/api','')+'/reading-state',{method:'PUT',body:JSON.stringify(value),keepalive:final}).then(()=>{if(live)setSaveError('');}).catch(()=>{if(live)setSaveError('阅读位置尚未保存，请检查服务连接。');});pending=pending.then(send);}
  setLoading(true);setError('');setDoc(null);setOutline([]);setSelection(null);setScanHint('');textCache.current.clear();
  void(async()=>{try{
   const pdfjs=await import('pdfjs-dist');(globalThis as any).pdfjsLib=pdfjs;
   const {PDFViewer,EventBus,PDFLinkService,PDFFindController}=await import('pdfjs-dist/web/pdf_viewer.mjs');
   if(!live||!container.current||!viewerElement.current)return;
   pdfjs.GlobalWorkerOptions.workerSrc=workerUrl;
   const events=new EventBus(),link=new PDFLinkService({eventBus:events,externalLinkTarget:2}),find=new PDFFindController({eventBus:events,linkService:link});
   const l10n={getLanguage:()=> 'zh-CN',getDirection:()=> 'ltr',get:async(_key:string,_args:any,fallback:string)=>fallback||'',translate:async()=>{},pause:()=>{},resume:()=>{}};
   const instance=new PDFViewer({container:container.current,viewer:viewerElement.current,eventBus:events,linkService:link,findController:find,textLayerMode:1,annotationMode:0,l10n:l10n as any,maxCanvasPixels:16777216,abortSignal:abort.signal});
   viewer.current=instance;bus.current=events;links.current=link;link.setViewer(instance);
   let jumped='';
   const currentAttachment=url.split('/').at(-1);
   function draw(){
    if(!live)return;
    const items=sourceRef.current.filter(a=>a.attachment_id===currentAttachment&&a.pdf_sha256===sha256&&a.available);
    const focus=focusRef.current;
    if(focus&&focus.attachment_id===currentAttachment&&focus.pdf_sha256===sha256&&!items.some(a=>a.id===focus.id))items.push(focus);
    viewerElement.current?.querySelectorAll('.source-layer').forEach(layer=>layer.remove());
    for(const canvas of viewerElement.current?.querySelectorAll('.canvasWrapper canvas')||[]){
     const div=canvas.closest<HTMLElement>('.page');if(!div)continue;
     const i=Number(div.dataset.pageNumber)-1,pv=instance.getPageView(i);if(!pv?.div)continue;
     const layer=document.createElement('div');layer.className='source-layer';
     const scaleX=pv.div.clientWidth/pv.viewport.width,scaleY=pv.div.clientHeight/pv.viewport.height;
     for(const a of items){
      const rects=a.rects.filter(r=>r.page===i+1);if(!rects.length)continue;
      const active=focus?.id===a.id&&Date.now()<focusUntil.current;
      if(a.annotation||active)for(const item of rects){const rect=pdfRect(pv.viewport.convertToViewportRectangle(item.rect));const mark=document.createElement('div');mark.className='source-highlight'+(active?' source-focus':'');mark.style.cssText=`left:${rect[0]*scaleX}px;top:${rect[1]*scaleY}px;width:${(rect[2]-rect[0])*scaleX}px;height:${(rect[3]-rect[1])*scaleY}px;background:${a.annotation?.color||'#8db9da'};`;layer.append(mark);}
      const rect=pdfRect(pv.viewport.convertToViewportRectangle(rects[0].rect));const marker=document.createElement('button');marker.type='button';marker.className='source-marker';marker.textContent=a.annotation?'●':'◇';marker.title=`${a.annotation?.label||'原文出处'} · ${a.cleaned_text.slice(0,100)}`;marker.setAttribute('aria-label',`打开第 ${i+1} 页批注与关联知识`);marker.style.top=Math.max(0,rect[1]*scaleY)+'px';marker.style.background=a.annotation?.color||'#8db9da';marker.addEventListener('click',event=>{event.stopPropagation();selectRef.current?.(a);});layer.append(marker);
     }
     if(layer.childElementCount)pv.div.append(layer);
    }
   }
   drawRef.current=draw;
   jumpRef.current=()=>{const a=focusRef.current;if(!a||(a.navigation||a.id)===jumped||!pdf||!initialized)return;if(a.attachment_id!==currentAttachment||a.pdf_sha256!==sha256){onError(new Error('来源 PDF 版本不符，已阻止定位'));return;}if(a.page>pdf.numPages){onError(new Error('来源页码超出当前 PDF，定位信息已失效'));return;}
    jumped=a.navigation||a.id;focusUntil.current=Date.now()+8000;root.current?.scrollIntoView({block:'start'});instance.currentPageNumber=a.page;requestAnimationFrame(()=>{const pv=instance.getPageView(a.page-1),rect=a.rects.find(r=>r.page===a.page);if(pv&&container.current&&rect){const pos=pdfRect(pv.viewport.convertToViewportRectangle(rect.rect));container.current.scrollTop=pv.div.offsetTop+pos[1]*pv.div.clientHeight/pv.viewport.height-100;container.current.scrollLeft=Math.max(0,pv.div.offsetLeft+pos[0]-30);}draw();clearTimeout(focusTimer.current);focusTimer.current=setTimeout(()=>{if(focusRef.current?.id===a.id)draw();},8000);});};
   const saved:Position=await api(url.replace('/api','')+'/reading-state');if(!live)return;position.current=saved;
   events.on('pagesinit',()=>{if(!live)return;instance.pagesRotation=saved.rotation||0;instance.currentScaleValue=saved.scale;instance.currentPageNumber=Math.min(saved.page,pdf!.numPages);setPage(instance.currentPageNumber);setScale(saved.scale);requestAnimationFrame(()=>requestAnimationFrame(()=>{if(!live)return;const p=instance.getPageView(instance.currentPageNumber-1);if(p&&container.current)container.current.scrollTop=p.div.offsetTop+saved.offset*p.div.clientHeight;initialized=true;jumpRef.current();draw();}));});
   events.on('pagerendered',(e:any)=>{if(live){setLoading(false);draw();if(e.error)setError('PDF 页面无法渲染：'+e.error.message);}});
   function scanStatus(pageNumber:number){const text=instance.getPageView(pageNumber-1)?.div.querySelector('.textLayer');setScanHint(text&&!text.textContent?.trim()?'此页未检测到可提取文本，无法选词。扫描件请先在外部进行 OCR。':'');}
   events.on('textlayerrendered',(e:any)=>{if(live&&e.pageNumber===instance.currentPageNumber)scanStatus(e.pageNumber);});
   events.on('pagechanging',(e:any)=>{if(live){setPage(e.pageNumber);scanStatus(e.pageNumber);}});
   events.on('scalechanging',(e:any)=>{if(live){setZoom(e.scale);setScale(instance.currentScaleValue);setSelection(null);requestAnimationFrame(draw);}});
   events.on('rotationchanging',()=>{setSelection(null);requestAnimationFrame(draw);});
   events.on('updateviewarea',()=>{if(!live||!initialized||!container.current)return;const p=instance.getPageView(instance.currentPageNumber-1);position.current={page:instance.currentPageNumber,scale:instance.currentScaleValue,rotation:instance.pagesRotation,offset:p?Math.min(1,Math.max(0,(container.current.scrollTop-p.div.offsetTop)/p.div.clientHeight)):0};clearTimeout(timer);timer=setTimeout(()=>persist(),650);});
   const counts=(e:any)=>{if(live)setMatches(e.matchesCount?.total?`${e.matchesCount.current} / ${e.matchesCount.total}`:'无匹配');};
   events.on('updatefindmatchescount',counts);events.on('updatefindcontrolstate',counts);
   if(sha256)await api(url.replace('/api','')+'/integrity?sha256='+sha256);
   if(!live)return;
   task=pdfjs.getDocument({url,cMapUrl:'/pdfjs/cmaps/',cMapPacked:true,standardFontDataUrl:'/pdfjs/standard_fonts/',useSystemFonts:true,isEvalSupported:false});
   pdf=await task.promise;if(!live)return;setDoc(pdf!);link.setDocument(pdf!);find.setDocument(pdf!);instance.setDocument(pdf!);
   const items=await pdf!.getOutline();if(live)setOutline(items||[]);
   observer=new ResizeObserver(()=>{if(['page-width','page-fit'].includes(instance.currentScaleValue))instance.currentScaleValue=instance.currentScaleValue;});observer.observe(container.current);
  }catch(e){if(live){setError('PDF 无法打开：'+String(e));setLoading(false);}}})();
  const flush=()=>persist(true);window.addEventListener('pagehide',flush);
  return()=>{clearTimeout(timer);clearTimeout(focusTimer.current);persist(true);live=false;abort.abort();observer?.disconnect();window.removeEventListener('pagehide',flush);viewer.current?.setDocument(null as any);viewer.current=null;links.current=null;bus.current=null;drawRef.current=()=>{};jumpRef.current=()=>{};void task?.destroy();};
 },[url]);
 useEffect(()=>{const escape=(event:KeyboardEvent)=>{if(event.key==='Escape'){setExpanded(false);setSelection(null);setMore(false);}};const outside=(event:PointerEvent)=>{if(!(event.target as HTMLElement).closest('.pdf-selection-toolbar'))setSelection(null);};window.addEventListener('keydown',escape);window.addEventListener('pointerdown',outside);return()=>{window.removeEventListener('keydown',escape);window.removeEventListener('pointerdown',outside);};},[]);
 async function selected(){
  if(!paperId||!sha256||!viewer.current||!doc)return;
  const native=window.getSelection();if(!native||native.isCollapsed||native.rangeCount!==1)return;
  const range=native.getRangeAt(0);if(!viewerElement.current?.contains(range.startContainer)||!viewerElement.current.contains(range.endContainer))return;
  const raw=native.toString();if(!raw.trim()||raw.length>200000)return;
  const rects:SelectionSource['rects']=[];const screen=Array.from(range.getClientRects());
  for(const el of viewerElement.current.querySelectorAll<HTMLElement>('.page')){
   const text=el.querySelector('.textLayer');if(!text||!range.intersectsNode(text))continue;
   const pageNumber=Number(el.dataset.pageNumber),pv=viewer.current.getPageView(pageNumber-1),box=el.getBoundingClientRect();if(!pv)continue;
   const left=box.left+el.clientLeft,top=box.top+el.clientTop;
   for(const r of screen){const x0=Math.max(r.left,left),y0=Math.max(r.top,top),x1=Math.min(r.right,left+el.clientWidth),y1=Math.min(r.bottom,top+el.clientHeight);if(x1-x0<.4||y1-y0<.4||y1-y0>Math.min(el.clientHeight*.3,180))continue;
    const a=pv.viewport.convertToPdfPoint((x0-left)*pv.viewport.width/el.clientWidth,(y0-top)*pv.viewport.height/el.clientHeight),b=pv.viewport.convertToPdfPoint((x1-left)*pv.viewport.width/el.clientWidth,(y1-top)*pv.viewport.height/el.clientHeight),rect=pdfRect([...a,...b]);if(!rects.some(q=>q.page===pageNumber&&q.rect.every((v,i)=>Math.abs(v-rect[i])<.3)))rects.push({page:pageNumber,rect});
   }
  }
  if(!rects.length||rects.length>2048)return;
  const bounds=range.getBoundingClientRect(),reader=root.current!.getBoundingClientRect(),width=Math.min(620,reader.width-20),x=Math.max(8,reader.left+8,Math.min(bounds.left,reader.right-width-8)),y=Math.max(8,reader.top+5,Math.min(bounds.bottom+8,reader.bottom-180,window.innerHeight-185));
  const source:SelectionSource={paper_id:paperId,attachment_id:url.split('/').at(-1)!,pdf_sha256:sha256,page:Math.min(...rects.map(r=>r.page)),raw_text:raw,cleaned_text:cleanSelection(raw),context:'',section:'',printed_page:'',notes:'',rects};
  setMore(false);setSelection({source,x,y});
  if(new Set(rects.map(r=>r.page)).size===1){const p=source.page;if(!textCache.current.has(p)){if(textCache.current.size>=8)textCache.current.delete(textCache.current.keys().next().value!);textCache.current.set(p,doc.getPage(p).then(page=>page.getTextContent()).then(text=>cleanSelection(text.items.map(i=>'str'in i?i.str+('hasEOL'in i&&i.hasEOL?'\n':' '):'').join(''))));}
   try{const text=await textCache.current.get(p)!,index=text.indexOf(source.cleaned_text);if(index>=0)setSelection(old=>old?.source===source?{...old,source:{...source,context:text.slice(Math.max(0,index-180),Math.min(text.length,index+source.cleaned_text.length+180))}}:old);}catch{}
  }
 }
 function capture(action:CaptureAction){if(!selection)return;if(document.fullscreenElement)void document.exitFullscreen();setExpanded(false);onCapture?.(selection.source,action);setSelection(null);}
 function go(value:number){if(viewer.current&&doc)viewer.current.currentPageNumber=Math.min(doc.numPages,Math.max(1,value));}
 function resize(value:string){if(viewer.current)viewer.current.currentScaleValue=value;}
 function search(value:string,type='',previous=false){setQuery(value);if(!value)setMatches('');bus.current?.dispatch('find',{source:root.current,type,query:value,phraseSearch:true,caseSensitive:false,entireWord:false,highlightAll:true,findPrevious:previous,matchDiacritics:false});}
 function outlineItems(items:Outline[],depth=0):React.ReactNode{return items.map((item,i)=><div key={depth+'-'+i}><button className="pdf-outline-item" style={{paddingLeft:10+depth*12}} onClick={()=>void links.current?.goToDestination(item.dest)}>{item.title}</button>{outlineItems(item.items||[],depth+1)}</div>);}
 return <section ref={root} className={'pdf-reader '+(expanded?'reader-expanded':'')} aria-label="论文 PDF 阅读器"><div className="pdf-reader-toolbar">
 <button className="icon-button" title="页面缩略图" onClick={()=>setSide(side==='thumbnails'?'':'thumbnails')}><Sidebar size={17}/></button><button className="ghost" onClick={()=>setSide(side==='outline'?'':'outline')}>目录</button>
 <button className="icon-button" title="PDF 上一页" disabled={page<=1} onClick={()=>go(page-1)}><ChevronLeft size={16}/></button><input aria-label="PDF 页码" type="number" min={1} max={doc?.numPages||1} value={page} onChange={e=>go(Number(e.target.value)||1)}/><span>/ {doc?.numPages||'…'}</span><button className="icon-button" title="PDF 下一页" disabled={!doc||page>=doc.numPages} onClick={()=>go(page+1)}><ChevronRight size={16}/></button>
 <button className="icon-button" title="缩小 PDF" onClick={()=>resize(String(Math.max(.25,zoom-.25)))}><Minus size={15}/></button><select aria-label="PDF 缩放模式" value={['page-width','page-fit'].includes(scale)?scale:'custom'} onChange={e=>resize(e.target.value)}><option value="page-width">适应宽度</option><option value="page-fit">适应整页</option><option value="custom" disabled>{Math.round(zoom*100)}%</option>{[.5,1,1.5,2,3].map(n=><option key={n} value={n}>{n*100}%</option>)}</select><button className="icon-button" title="放大 PDF" onClick={()=>resize(String(Math.min(5,zoom+.25)))}><Plus size={15}/></button>
 <button className="ghost" title="顺时针旋转 90 度" onClick={()=>{if(viewer.current)viewer.current.pagesRotation=(viewer.current.pagesRotation+90)%360;}}>旋转</button><button className="icon-button" title="全屏阅读" onClick={()=>{if(expanded){setExpanded(false);return;}if(window.document.fullscreenElement)void window.document.exitFullscreen();else void root.current?.requestFullscreen().catch(()=>setExpanded(true));}}><Maximize size={16}/></button><a href={url} className="icon-button" title="打开原始 PDF" target="_blank" rel="noreferrer"><Download size={15}/></a></div>
 <div className="pdf-search"><Search size={15}/><input aria-label="搜索 PDF 文本" placeholder="搜索论文文本（扫描件需 OCR）" value={query} onChange={e=>search(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')search(query,'again',e.shiftKey);}}/><span>{matches}</span><button className="icon-button" title="上一个搜索结果" onClick={()=>search(query,'again',true)}><ChevronLeft size={15}/></button><button className="icon-button" title="下一个搜索结果" onClick={()=>search(query,'again')}><ChevronRight size={15}/></button></div>
 {(saveError||scanHint)&&<div className="pdf-warning">{saveError||scanHint}</div>}<div className="pdf-reader-body">{side&&<aside className="pdf-reader-sidebar">{side==='outline'?(outline.length?outlineItems(outline):<p>此 PDF 没有内置目录。</p>):doc&&Array.from({length:doc.numPages},(_,i)=><Thumbnail key={i} doc={doc} page={i+1} onClick={()=>go(i+1)}/>)}</aside>}<div className="pdf-view-shell"><div ref={container} className="pdf-scroll-container" onPointerUp={()=>void selected()} onKeyUp={e=>{if(e.shiftKey)void selected();}} onScroll={()=>setSelection(null)}><div ref={viewerElement} className="pdfViewer"/></div>{loading&&!error&&<div className="pdf-loading">正在渲染本地 PDF…</div>}{error&&<p className="notice error pdf-error" role="alert">{error}</p>}</div></div>
 {selection&&<div role="toolbar" aria-label="原文选区操作" className="pdf-selection-toolbar" style={{left:selection.x,top:selection.y,width:Math.min(620,(root.current?.clientWidth||640)-20)}} onPointerDown={e=>e.preventDefault()}><button onClick={()=>void navigator.clipboard.writeText(selection.source.raw_text).catch(onError)}>复制</button><button onClick={()=>capture('highlight')}>高亮</button><button onClick={()=>capture('vocabulary')}>科研英语</button><button onClick={()=>capture('note')}>添加笔记</button><button onClick={()=>capture('prompt')}>ChatGPT 提问</button><button onClick={()=>setMore(!more)}>更多 {more?'−':'+'}</button>{more&&<>{([['mathematics','数学知识'],['algorithm','算法知识'],['idea','科研想法'],['question','待解决问题']] as const).map(([action,label])=><button key={action} onClick={()=>capture(action)}>{label}</button>)}</>}</div>}
 </section>;
}
