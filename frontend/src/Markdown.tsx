import {useEffect,useRef,useState} from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import rehypeHighlight from 'rehype-highlight';
import 'katex/dist/katex.min.css';
import 'highlight.js/styles/github-dark.css';

let initialized=false;
let renderQueue=Promise.resolve();
function Diagram({code}:{code:string}){
  const ref=useRef<HTMLDivElement>(null);const [error,setError]=useState('');
  useEffect(()=>{let live=true;renderQueue=renderQueue.then(async()=>{try{const {default:mermaid}=await import('mermaid');if(!initialized){mermaid.initialize({startOnLoad:false,securityLevel:'strict',theme:'neutral',suppressErrorRendering:true});initialized=true;}const {svg}=await mermaid.render('m'+crypto.randomUUID().replaceAll('-',''),code);if(live&&ref.current)ref.current.innerHTML=svg;}catch{if(live)setError('Mermaid 语法错误，请检查流程图代码。');}});return()=>{live=false;};},[code]);
  return <div className="diagram">{error?<pre>{error}{'\n'}{code}</pre>:<div ref={ref}/>}</div>;
}
export function Markdown({text,onOpen}:{text:string;onOpen?:(id:string)=>void}){
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm,remarkMath]} rehypePlugins={[[rehypeKatex,{strict:false,trust:false}],rehypeHighlight]} components={{
    code:({className,children,...props})=>className?.includes('language-mermaid')?<Diagram code={String(children)}/>:<code className={className} {...props}>{children}</code>,
    a:({href,children})=>href?.startsWith('#node/')?<a href={href} onClick={e=>{e.preventDefault();onOpen?.(href.slice(6));}}>{children}</a>:<a href={href} target="_blank" rel="noopener noreferrer">{children}</a>,
    img:({src,alt})=>src?.startsWith('/api/attachments/')?<img src={src} alt={alt} loading="lazy"/>:<span className="muted">[外部图片未加载：{alt}，请上传本地附件]</span>
  }}>{text}</ReactMarkdown></div>;
}
