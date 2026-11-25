import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,waitFor} from '@testing-library/react';
import {cleanSelection,insertExcerpt,sourceMarkdown,readingPrompt,pdfRect,makeCapture,type SelectionSource,type Source} from '../src/reading';
import {Detail} from '../src/Detail';
import type {Node} from '../src/types';
import {api,post} from '../src/api';

const fixture=vi.hoisted(()=>({paper_id:'11111111-1111-1111-1111-111111111111',attachment_id:'22222222-2222-2222-2222-222222222222',pdf_sha256:'a'.repeat(64),page:4,raw_text:'A learned differentiable model.',cleaned_text:'A learned differentiable model.',context:'',section:'',printed_page:'',notes:'',rects:[{page:4,rect:[72,400,250,414] as [number,number,number,number]}]}));
vi.mock('../src/api',()=>({api:vi.fn(),post:vi.fn(),download:vi.fn()}));
vi.mock('../src/desktop',()=>({desktop:undefined}));
vi.mock('../src/Markdown',()=>({Markdown:({text}:{text:string})=><div>{text}</div>}));
vi.mock('../src/PdfViewer',()=>({PdfViewer:({onCapture}:{onCapture:(s:SelectionSource,a:string)=>void})=><button onClick={()=>onCapture(fixture,'note')}>选文添加到论文笔记</button>}));
afterEach(()=>{cleanup();vi.clearAllMocks();localStorage.clear();});
describe('reading text, citations and prompts',()=>{
 it('retains a raw source while cleaning line hyphens, soft hyphens and spacing',()=>{const raw='A differen-\ntiable  world\nmodel\u00ad.';expect(cleanSelection(raw)).toBe('A differentiable world model.');expect(raw).toContain('-\n');expect(cleanSelection('model-based control')).toBe('model-based control');});
 it('keeps separate line and cross-page rectangles and normalizes either axis order',()=>{expect(pdfRect([300,700,100,50])).toEqual([100,50,300,700]);const source={...fixture,rects:[...fixture.rects,{page:5,rect:[20,30,40,50] as [number,number,number,number]}]};const prompt=readingPrompt('Paper title',source,'sentence');expect(prompt).toContain('第 4、5 页');expect(source.rects).toHaveLength(2);});
 it('creates six distinct editable prompts with accurate sources and no fabricated section',()=>{for(const mode of ['vocabulary','sentence','mathematics','algorithm','research','custom']){const prompt=readingPrompt('Actual paper',fixture,mode);expect(prompt).toContain('Actual paper');expect(prompt).toContain('PDF 第 4 页');expect(prompt).toContain(fixture.cleaned_text);expect(prompt).not.toContain('Introduction');}expect(readingPrompt('P',fixture,'vocabulary')).toContain('暂时不要直接翻译');});
 it('makes exported excerpts readable outside the app and labels AI explanations',()=>{const md=sourceMarkdown(fixture,'anchor-id','My explanation','ai');expect(md).toContain('> '+fixture.raw_text);expect(md).toContain('[PDF 第 4 页](#source/anchor-id)');expect(md).toContain('AI 辅助解释（需核对）');expect(md).not.toContain('论文作者结论');});
 it('inserts into the latest draft at a cursor or heading without replacing other sections',()=>{const body='## One\n\nUnsaved edits\n\n## Two\n\nKeep this';expect(insertExcerpt(body,'EXCERPT',body.indexOf('Unsaved'),'cursor')).toContain('EXCERPTUnsaved edits');const result=insertExcerpt(body,'EXCERPT\n',0,'## One');expect(result).toContain('Unsaved edits\n\nEXCERPT\n## Two');expect(result).toContain('Keep this');});
 it('retains annotation revision when recreating a deleted highlight',()=>{expect(makeCapture(fixture,'highlight','Paper',{id:'anchor',annotation:null,annotation_revision:4} as Source).annotation_version).toBe(4);});
});

describe('paper editor and reading capture integration',()=>{
 it('adds a quote to unsaved editor content and leaves the reader mounted',async()=>{
  const node:Node={id:fixture.paper_id,kind:'paper',title:'Paper',status:'reading',tags:[],metadata:{},version:1,created_at:'2026-01-01',updated_at:'2026-01-01',markdown:'## Notes\n\nOriginal',attachments:[{id:fixture.attachment_id,media_type:'application/pdf',name:'Paper.pdf',size:100,sha256:fixture.pdf_sha256}],relations:[]};
  const source={...fixture,id:'anchor-id',nodes:[],annotation:null,version:1,paper_title:'Paper',available:true};
  vi.mocked(api).mockImplementation(async(path,opts)=>{
   if(path.endsWith('reading-workspace'))return opts?{}:{mode:'split',split_width:55,panel_tab:'notes',selected_anchor:'',selected_node:'',attachment_id:fixture.attachment_id,draft:null};
   if(path==='/categories'||path.endsWith('/sources'))return [];
   if(path.endsWith('/reading'))return {sources:[],nodes:[]};
   if(path==='/sources/anchor-id')return source;
   if(path==='/nodes/'+node.id)return {...node,version:opts?2:1};
   return {items:[]};
  });
  vi.mocked(post).mockImplementation(async(path)=>path==='/sources'?source:{});
  const view=render(<Detail initial={node} onOpen={vi.fn()} onBack={vi.fn()} onChanged={vi.fn()} onError={vi.fn()} guard={{current:null}}/>);
  await waitFor(()=>expect(view.getByText('选文添加到论文笔记')).toBeTruthy());
  const editor=view.getByLabelText('Markdown 编辑器') as HTMLTextAreaElement;
  fireEvent.change(editor,{target:{value:'## Notes\n\nUnsaved handwritten explanation'}});editor.setSelectionRange(editor.value.length,editor.value.length);fireEvent.select(editor);
  fireEvent.click(view.getByText('选文添加到论文笔记'));
  fireEvent.change(view.getByLabelText('解释 / 个人理解 / AI 回答（Markdown / LaTeX）'),{target:{value:'Additional understanding'}});
  fireEvent.click(view.container.querySelector('.capture-panel footer button:last-child')!);
  await waitFor(()=>expect(editor.value).toContain('#source/anchor-id'));
  expect(editor.value).toContain('Unsaved handwritten explanation');expect(editor.value).toContain('Additional understanding');expect(view.getByText('选文添加到论文笔记')).toBeTruthy();
 });
});
