import type {Kind,Node} from './types';

export type PageRect={page:number;rect:[number,number,number,number]};
export type SelectionSource={paper_id:string;attachment_id:string;pdf_sha256:string;page:number;raw_text:string;cleaned_text:string;context:string;section:string;printed_page:string;notes:string;rects:PageRect[]};
export type Annotation={id:string;anchor_id:string;color:string;label:string;markdown:string;version:number;created_at:string;updated_at:string};
export type Source=SelectionSource&{id:string;version:number;paper_title:string;available:boolean;created_at:string;updated_at:string;annotation:Annotation|null;annotation_revision?:number;nodes:Node[];navigation?:string};
export type CaptureAction=Exclude<Kind,'paper'>|'note'|'highlight'|'prompt';
export type CaptureDraft={selection:SelectionSource;anchor_id?:string;action:CaptureAction;title:string;metadata:Node['metadata'];markdown:string;provenance:'personal'|'ai'|'paper'|'external';target_id:string;target_version:number;mode:'new'|'append'|'edit';color:string;label:string;annotation_version:number;insertion:string;prompt_mode:string;prompt:string};
export type ReadingWorkspace={mode:'note'|'pdf'|'split';split_width:number;panel_tab:string;selected_anchor:string;selected_node:string;attachment_id:string;draft:CaptureDraft|null};
export const defaultReading:ReadingWorkspace={mode:'note',split_width:55,panel_tab:'notes',selected_anchor:'',selected_node:'',attachment_id:'',draft:null};
export const highlightColors=[['#e6cb73','重要内容'],['#8db9da','算法与方法'],['#a3c7a0','关键结论'],['#b6a0ce','数学与理论'],['#df9d9f','疑问']];
export const captureNames:Record<CaptureAction,string>={vocabulary:'添加科研英语',mathematics:'创建数学知识',algorithm:'创建算法知识',idea:'记录科研想法',question:'创建待解决问题',note:'添加到论文笔记',highlight:'高亮与批注',prompt:'ChatGPT 提问'};
export function cleanSelection(text:string){return text.replace(/\u00ad/g,'').replace(/([\p{L}])-\s*\r?\n\s*(?=[\p{Ll}])/gu,'$1').replace(/\s+/g,' ').trim();}
export function pdfRect(points:number[]):[number,number,number,number]{return [Math.min(points[0],points[2]),Math.min(points[1],points[3]),Math.max(points[0],points[2]),Math.max(points[1],points[3])];}
export const promptModes=[['vocabulary','英文词汇解释'],['sentence','英文句子理解'],['mathematics','数学公式与理论'],['algorithm','算法原理'],['research','科研思考'],['custom','自定义问题']];
const instructions:Record<string,string>={vocabulary:'请解释这段内容中影响理解的英文生词、短语和专业术语，给出语境中的含义。暂时不要直接翻译整段内容。',sentence:'请解释这段英文的句子结构、关键表达和逻辑关系，帮助我理解原文。必要时再提供中文解释。',mathematics:'请结合论文上下文解释所选数学公式的符号、含义、推导过程、成立条件及在算法中的作用。',algorithm:'请解释这段内容所涉及的算法原理、模块关系、设计动机以及它在完整训练流程中的作用。',research:'请分析这段论文内容所涉及的关键假设、可能的局限性以及对机器人学习研究的启发。',custom:'我的问题：\n'};
export function readingPrompt(paper:string,source:SelectionSource,mode:string){const pages=[...new Set(source.rects.map(r=>r.page))].join('、');return `论文：${paper}\n位置：PDF 第 ${pages} 页${source.section?' · '+source.section:''}\n\n原文：\n${source.cleaned_text}\n${source.context?'\n可确认的页面上下文：\n'+source.context+'\n':''}\n${instructions[mode]||instructions.custom}\n\n请区分论文原文、你的推断与外部知识；信息不足时明确说明。`;}
export function sourceMarkdown(source:SelectionSource,id:string,explanation:string,provenance:string){const label={personal:'我的理解',ai:'AI 辅助解释（需核对）',paper:'论文原文摘录',external:'外部参考资料'}[provenance]||'我的理解';return `\n\n${source.raw_text.split(/\r?\n/).map(s=>'> '+s).join('\n')}\n\n来源：[PDF 第 ${[...new Set(source.rects.map(r=>r.page))].join('、')} 页](#source/${id})${source.section?' · '+source.section:''}\n\n**${label}：**\n\n${explanation}\n`;}
/** Insert against the latest editor body, retaining all unsaved edits. */
export function insertExcerpt(body:string,addition:string,cursor:number,heading:string){
 let index=Math.min(Math.max(cursor,0),body.length);
 if(heading&&heading!=='cursor'){const lines=body.split('\n');let offset=0,found=false;for(const line of lines){if(found&&/^#{1,6}\s/.test(line)){index=offset;break;}offset+=line.length+1;if(line===heading){index=body.length;found=true;}}}
 return body.slice(0,index)+addition+body.slice(index);
}
export function makeCapture(selection:SelectionSource,action:CaptureAction,paper:string,source?:Source):CaptureDraft{return {selection,anchor_id:source?.id,action,title:selection.cleaned_text.slice(0,action==='vocabulary'?200:100),metadata:{priority:3,mastery:0,...(action==='vocabulary'?{examples:[selection.context||selection.cleaned_text],meaning:'',contextual_meaning:'',vocabulary_category:'general_academic'}:{})},markdown:source?.annotation?.markdown||'',provenance:'personal',target_id:'',target_version:0,mode:'new',color:source?.annotation?.color||highlightColors[0][0],label:source?.annotation?.label||highlightColors[0][1],annotation_version:source?.annotation_revision||source?.annotation?.version||0,insertion:'cursor',prompt_mode:'vocabulary',prompt:readingPrompt(paper,selection,'vocabulary')};}
export function openSource(id:string){window.dispatchEvent(new CustomEvent('rh-open-source',{detail:id}));}
