import {desktop} from './desktop';
import {useEffect,useRef,useState} from 'react';
import {ArrowLeft,Check,Download,FileText,History,Link2,LoaderCircle,Plus,Save,Trash2,Upload,X} from 'lucide-react';
import {api,post,download} from './api';
import {Markdown} from './Markdown';
import {PdfViewer} from './PdfViewer';
import {fields} from './fields';
import {Node,Meta,Category,names,states,labels,relationTypes,relationLabels,fmtDate} from './types';

type Form={kind:Node['kind'];title:string;status:string;tags:string[];metadata:Meta;markdown:string};
const toForm=(n:Node):Form=>({kind:n.kind,title:n.title,status:n.status,tags:n.tags,metadata:n.metadata,markdown:n.markdown||''});

export function Detail({initial,onOpen,onBack,onChanged,guard,onError}:{initial:Node;onOpen:(id:string)=>void;onBack:()=>void;onChanged:()=>void;guard:React.MutableRefObject<null|(()=>Promise<boolean>)>;onError:(e:unknown)=>void}){
  const [form,setForm]=useState<Form>(toForm(initial));
  const [tagsText,setTagsText]=useState(initial.tags.join(', '));
  const latest=useRef(form),persisted=useRef(JSON.stringify(form)),version=useRef(initial.version),saving=useRef(false),blocked=useRef(false);
  const [saveState,setSaveState]=useState('已保存'),[draft,setDraft]=useState<Form|null>(null),[saveError,setSaveError]=useState('');
  const [tab,setTab]=useState('note'),[mode,setMode]=useState('split'),[extras,setExtras]=useState(initial),[readingMode,setReadingMode]=useState<'note'|'pdf'|'split'>('note'),[history,setHistory]=useState<any[]>([]);
  const [categories,setCategories]=useState<Category[]>([]),[linkQuery,setLinkQuery]=useState(''),[targets,setTargets]=useState<Node[]>([]),[target,setTarget]=useState(''),[relationType,setRelationType]=useState('related_to'),[description,setDescription]=useState(''),[evidence,setEvidence]=useState('');
  const [mergeId,setMergeId]=useState(''),[busy,setBusy]=useState(false);
  const draftKey='rh-draft-'+initial.id;
  const dirty=()=>JSON.stringify(latest.current)!==persisted.current;
  function update(next:Form){latest.current=next;setForm(next);setSaveState('待保存');try{const value=JSON.stringify({form:next,baseVersion:version.current});localStorage.setItem(draftKey,value);void desktop?.writeCache(draftKey,value).catch(()=>setSaveError('桌面草稿缓存写入失败，请及时保存笔记。'));}catch{setSaveError('浏览器草稿空间不足，请及时保存或下载草稿。');}}
  const save=async():Promise<boolean>=>{
    if(blocked.current)return false;
    if(saving.current){return false;}
    if(!dirty())return true;
    const sent=latest.current,serialized=JSON.stringify(sent);
    saving.current=true;setSaveState('正在保存');
    try{
      const result=await api<Node>('/nodes/'+initial.id,{method:'PUT',body:JSON.stringify({...sent,expected_version:version.current})});
      version.current=result.version;persisted.current=serialized;setSaveState(JSON.stringify(latest.current)===serialized?'已保存':'待保存');setSaveError('');
      if(JSON.stringify(latest.current)===serialized){localStorage.removeItem(draftKey);await desktop?.writeCache(draftKey,null);}
      onChanged();return JSON.stringify(latest.current)===serialized;
    }catch(e){setSaveState('保存失败');setSaveError(String(e));if(String(e).includes('已有更新'))blocked.current=true;return false;}finally{saving.current=false;}
  };
  const saveRef=useRef(save);saveRef.current=save;
  useEffect(()=>{
    try{const local=JSON.parse(localStorage.getItem(draftKey)||'null');if(local?.form&&JSON.stringify(local.form)!==persisted.current)setDraft(local.form);}catch{ /* invalid browser draft does not affect disk */ }
    void desktop?.readCache(draftKey).then(value=>{if(!value||dirty())return;try{const cached=JSON.parse(value);if(cached?.form&&JSON.stringify(cached.form)!==persisted.current)setDraft(cached.form);}catch{}}).catch(onError);
    api<Category[]>('/categories').then(setCategories).catch(onError);
    guard.current=()=>saveRef.current();
    const interval=setInterval(()=>{if(dirty()&&!saving.current&&!blocked.current)void saveRef.current();},1400);
    const before=(e:BeforeUnloadEvent)=>{if(dirty()){e.preventDefault();e.returnValue='';}};
    const key=(e:KeyboardEvent)=>{if((e.ctrlKey||e.metaKey)&&e.key==='s'){e.preventDefault();void saveRef.current();}};
    window.addEventListener('beforeunload',before);window.addEventListener('keydown',key);
    return()=>{clearInterval(interval);guard.current=null;window.removeEventListener('beforeunload',before);window.removeEventListener('keydown',key);};
  },[]);
  useEffect(()=>{let live=true;const t=setTimeout(()=>api<{items:Node[]}>('/nodes?q='+encodeURIComponent(linkQuery)).then(r=>{if(live)setTargets(r.items.filter(n=>n.id!==initial.id));}).catch(onError),250);return()=>{live=false;clearTimeout(t);};},[linkQuery]);
  const meta=(key:string,value:Meta[string])=>update({...latest.current,metadata:{...latest.current.metadata,[key]:value}});
  async function reloadExtras(){const n=await api<Node>('/nodes/'+initial.id);setExtras(n);}
  async function attach(file:File){setBusy(true);try{const data=new FormData();data.append('file',file);const a=await api<{id:string;name:string;url:string}>('/nodes/'+initial.id+'/attachments',{method:'POST',body:data});if(file.type.startsWith('image/'))update({...latest.current,markdown:latest.current.markdown+`\n\n![本地图片](${a.url})\n`});await reloadExtras();onChanged();}catch(e){onError(e);}finally{setBusy(false);}}
  async function link(){if(!target)return;try{await post('/relations',{source:initial.id,target,type:relationType,description,evidence});setTarget('');setDescription('');setEvidence('');await reloadExtras();onChanged();}catch(e){onError(e);}}
  async function remove(){if(!window.confirm('将此条目移入回收站？正文、附件和修改历史会保留。'))return;if(!await saveRef.current())return;try{await api('/nodes/'+initial.id+'?expected_version='+version.current,{method:'DELETE'});onChanged();onBack();}catch(e){onError(e);}}
  async function showHistory(){if(!await saveRef.current())return;try{setHistory(await api('/nodes/'+initial.id+'/history'));setTab('history');}catch(e){onError(e);}}
  async function merge(){const selected=targets.find(n=>n.id===mergeId);if(!selected||!window.confirm(`将当前条目合并到「${selected.title}」？原条目将进入回收站，正文以补充段落保留。`))return;if(!await saveRef.current())return;try{await post('/merge',{source_id:initial.id,target_id:mergeId,source_version:version.current,target_version:selected.version});onChanged();onOpen(mergeId);}catch(e){onError(e);}}
  const pdfFile=extras.attachments?.find(a=>a.media_type==='application/pdf');
  return <div className={'detail '+(readingMode==='pdf'?'pdf-only':'')}>
    <div className="detail-top"><button className="ghost" onClick={onBack}><ArrowLeft size={17}/> {names[form.kind]}</button><span className={'save-state '+(saveError?'danger':'')}>{saveState==='正在保存'?<LoaderCircle size={14} className="spin"/>:<Check size={14}/>} {saveState}</span><button className="ghost" onClick={()=>void saveRef.current()}><Save size={16}/> 保存</button><a className="button ghost" href={'/api/export/nodes/'+initial.id}><Download size={16}/> 导出</a><button className="icon-button danger" title="移入回收站" onClick={remove}><Trash2 size={17}/></button></div>
    {draft&&<div className="notice">发现未保存的本地草稿。<button onClick={()=>{update(draft);setDraft(null);}}>恢复草稿</button><button className="ghost" onClick={()=>{localStorage.removeItem(draftKey);void desktop?.writeCache(draftKey,null).catch(onError);setDraft(null);}}>舍弃草稿</button></div>}
    {saveError&&<div className="notice error">{saveError}<button onClick={()=>download(new Blob([JSON.stringify(latest.current,null,2)],{type:'application/json'}),'research-hub-draft.json')}>下载草稿</button><button onClick={()=>{if(window.confirm('草稿已保留在本机浏览器。重新加载服务器版本？'))window.location.reload();}}>重新加载</button></div>}
    <input className="title-input" aria-label="条目标题" value={form.title} onChange={e=>update({...latest.current,title:e.target.value})}/>
    <div className="detail-meta"><select aria-label="当前状态" value={form.status} onChange={e=>{const next={...latest.current,status:e.target.value};if(form.kind==='question'&&e.target.value==='resolved')next.metadata={...next.metadata,resolved_at:new Date().toISOString()};update(next);}}>{states[form.kind].map(s=><option key={s} value={s}>{labels[s]}</option>)}</select><input aria-label="标签" placeholder="添加标签，以逗号分隔" value={tagsText} onChange={e=>{setTagsText(e.target.value);update({...latest.current,tags:e.target.value.split(/[,，]/).map(s=>s.trim()).filter(Boolean)});}}/><span className="muted">更新于 {fmtDate(initial.updated_at)} · v{version.current}</span></div>
    <div className="tabs"><button className={tab==='note'?'active':''} onClick={()=>setTab('note')}><FileText size={16}/> 知识笔记</button><button className={tab==='metadata'?'active':''} onClick={()=>setTab('metadata')}>基本信息</button><button className={tab==='history'?'active':''} onClick={showHistory}><History size={16}/> 修改历史</button></div>
    <div className="detail-columns"><section className="detail-main">
      {tab==='note'&&<><div className="editor-toolbar"><div className="segmented">{[['edit','编辑'],['split','分栏'],['preview','预览']].map(([k,v])=><button key={k} className={mode===k?'active':''} onClick={()=>setMode(k)}>{v}</button>)}</div><button className="ghost" onClick={()=>update({...latest.current,markdown:latest.current.markdown+'\n\n$$\n\\mathbb{E}_{x \\sim p(x)}[f(x)] = \\int f(x)p(x)\\,dx\n$$\n'})}>插入公式</button>{pdfFile&&<div className="segmented reading-modes">{[['note','仅笔记'],['pdf','仅 PDF'],['split','PDF 分栏']].map(([value,label])=><button key={value} className={readingMode===value?'active':''} onClick={()=>setReadingMode(value as 'note'|'pdf'|'split')}>{label}</button>)}</div>}</div>
      <div className={'editor-layout '+(readingMode!=='note'&&pdfFile?'with-pdf':'')}>{readingMode!=='note'&&pdfFile&&<PdfViewer url={'/api/attachments/'+pdfFile.id}/>}{readingMode!=='pdf'&&<div className={'editor '+mode}>{mode!=='preview'&&<textarea aria-label="Markdown 编辑器" spellCheck={false} value={form.markdown} onChange={e=>update({...latest.current,markdown:e.target.value})}/>} {mode!=='edit'&&<Markdown text={form.markdown||'*开始记录你的理解。*'} onOpen={onOpen}/>}</div>}</div><p className="editor-hint">支持 Markdown · LaTeX · Mermaid · 本地图片 · [内部链接](#node/条目ID) · Ctrl+S 保存</p></>}
      {tab==='metadata'&&<div className="fields">{fields[form.kind].map(f=><label className={f.type==='long'?'wide':''} key={f.key}><span>{f.label}{f.type==='list'&&<small> 每行一条</small>}</span>{f.type==='bool'?<input type="checkbox" checked={!!form.metadata[f.key]} onChange={e=>meta(f.key,e.target.checked)}/>:f.type==='select'?<select value={String(form.metadata[f.key]||f.options?.[0][0]||'')} onChange={e=>meta(f.key,e.target.value)}>{f.options?.map(([k,v])=><option key={k} value={k}>{v}</option>)}</select>:f.type==='list'||f.type==='long'?<textarea rows={3} value={Array.isArray(form.metadata[f.key])?(form.metadata[f.key] as string[]).join('\n'):String(form.metadata[f.key]||'')} onChange={e=>meta(f.key,f.type==='list'?e.target.value.split('\n'):e.target.value)}/>:<input type={f.type==='number'?'number':f.type==='date'?'date':'text'} value={String(form.metadata[f.key]??'').slice(0,f.type==='date'?10:undefined)} min={f.key==='year'?1800:f.key==='mastery'?0:1} max={f.key==='year'?2200:5} onChange={e=>meta(f.key,f.type==='number'?(e.target.value?Number(e.target.value):null):f.type==='date'?(e.target.value||null):e.target.value)}/>}</label>)}
      {['mathematics','algorithm'].includes(form.kind)&&<fieldset className="wide"><legend>多级分类（允许多选）</legend>{categories.filter(c=>c.kind===form.kind).map(c=><label className="checkbox-line" key={c.id}><input type="checkbox" checked={(form.metadata.category_ids as string[]||[]).includes(c.id)} onChange={e=>meta('category_ids',e.target.checked?[...(form.metadata.category_ids as string[]||[]),c.id]:(form.metadata.category_ids as string[]||[]).filter(id=>id!==c.id))}/>{c.parent_id?'↳ ':''}{c.name}</label>)}</fieldset>}
      <div className="wide muted">定义、推导、训练流程、研究假设、实验设计与解决过程，请在知识笔记的对应章节中记录；章节可自由调整。</div></div>}
      {tab==='history'&&<div className="history">{history.map(h=><details key={h.id}><summary>版本 {h.version} · {fmtDate(h.created_at)} · {h.snapshot.title}</summary><button onClick={()=>{if(window.confirm('将此历史版本的正文和元数据恢复为新版本？')){update({...toForm(h.snapshot),markdown:h.markdown});setTab('note');}}}>恢复为新版本</button><Markdown text={h.markdown} onOpen={onOpen}/></details>)}</div>}
    </section><aside className="context-panel"><h3><Link2 size={16}/> 知识关联 <span>{extras.relations?.length||0}</span></h3>{!extras.relations?.length&&<p className="muted">让一个知识点成为下一次发现的起点。</p>}{extras.relations?.map(r=><div className="relation" key={r.id}><button className="relation-title" onClick={()=>onOpen(r.node!.id)}>{r.node?.title}</button><div className="muted">{r.direction==='incoming'?'对方 → 本条目':r.direction==='symmetric'?'双向':'本条目 → 对方'} · {relationLabels[r.type]}</div>{r.description&&<p>{r.description}</p>}{r.evidence&&<small>出处：{r.evidence}</small>}<button className="relation-remove" title="移除关联" onClick={async()=>{if(!window.confirm('移除这条关联？知识条目仍保留。'))return;try{await api('/relations/'+r.id,{method:'DELETE'});await reloadExtras();onChanged();}catch(e){onError(e);}}}><X size={12}/></button></div>)}
    <details className="add-link"><summary><Plus size={14}/> 建立关联</summary><input placeholder="检索已有知识" value={linkQuery} onChange={e=>setLinkQuery(e.target.value)}/><select aria-label="关联目标" value={target} onChange={e=>setTarget(e.target.value)}><option value="">选择知识条目</option>{targets.map(n=><option key={n.id} value={n.id}>{n.title} · {names[n.kind]}</option>)}</select><select value={relationType} onChange={e=>setRelationType(e.target.value)}>{relationTypes.map(t=><option key={t} value={t}>{relationLabels[t]} · {t}</option>)}</select><input placeholder="关联说明（可选）" value={description} onChange={e=>setDescription(e.target.value)}/><input placeholder="证据 / 原文页码（可选）" value={evidence} onChange={e=>setEvidence(e.target.value)}/><button disabled={!target} onClick={link}>添加关联</button></details>
    <h3><FileText size={16}/> 本地附件</h3>{extras.attachments?.map(a=><a className="attachment" key={a.id} href={'/api/attachments/'+a.id} target="_blank" rel="noreferrer"><FileText size={15}/><span>{a.name}</span><small>{(a.size/1024).toFixed(0)} KB</small></a>)}<label className="upload-button"><Upload size={15}/>{busy?'上传中…':'上传 PDF / 图片 / 附件'}<input type="file" disabled={busy} accept=".pdf,.png,.jpg,.jpeg,.webp,.txt,.csv,.py,.md,.json" onChange={e=>{if(e.target.files?.[0])void attach(e.target.files[0]);e.target.value='';}}/></label><p className="muted small">仅存储在你的工作空间 · 单个文件 ≤ 50 MB</p>
    {extras.review&&<><h3>复习记录</h3><p className="muted">下次复习：{fmtDate(extras.review.due_at)}<br/>连续成功：{extras.review.repetitions} · 遗忘：{extras.review.lapses}</p>{extras.review_history?.slice(0,10).map(h=><div className="small" key={h.id}>{fmtDate(h.reviewed_at)} · {labels[h.rating]} · {h.algorithm}</div>)}</>}
    {form.kind!=='vocabulary'&&<details className="add-link"><summary>合并重复知识</summary><p className="muted">当前条目正文附加到目标，元数据冲突会保留供人工检查。</p><input placeholder="搜索合并目标" value={linkQuery} onChange={e=>setLinkQuery(e.target.value)}/><select value={mergeId} onChange={e=>setMergeId(e.target.value)}><option value="">选择同类目标</option>{targets.filter(n=>n.kind===form.kind).map(n=><option key={n.id} value={n.id}>{n.title}</option>)}</select><button disabled={!mergeId} onClick={merge}>预览后确认合并</button></details>}
    </aside></div>
  </div>;
}
