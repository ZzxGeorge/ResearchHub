import {afterEach,describe,expect,it,vi} from 'vitest';
import {cleanup,fireEvent,render,waitFor} from '@testing-library/react';
import {Detail} from '../src/Detail';
import type {Node} from '../src/types';
const cache=vi.hoisted(()=>new Map<string,string>());
vi.mock('../src/desktop',()=>({desktop:{readCache:async(key:string)=>cache.get(key)||null,writeCache:async(key:string,value:string|null)=>{if(value===null)cache.delete(key);else cache.set(key,value);}}}));
vi.mock('../src/Markdown',()=>({Markdown:({text}:{text:string})=><div>{text}</div>}));
vi.mock('../src/api',()=>({api:vi.fn(async(path:string,options?:RequestInit)=>options?.method==='PUT'?{version:2}:path==='/categories'?[]:{items:[]}),post:vi.fn(),download:vi.fn()}));
afterEach(()=>{cleanup();cache.clear();localStorage.clear();});
describe('desktop draft recovery across loopback ports',()=>{
 it('recovers a native draft with empty browser storage and clears it after a successful note save',async()=>{
  const node:Node={id:'11111111-1111-1111-1111-111111111111',kind:'paper',title:'Paper',status:'reading',tags:[],metadata:{},version:1,markdown:'Server note',created_at:'2026-01-01',updated_at:'2026-01-01',relations:[],attachments:[]};
  const key='rh-draft-'+node.id;
  cache.set(key,JSON.stringify({form:{kind:node.kind,title:node.title,status:node.status,tags:[],metadata:{},markdown:'Handwritten draft from the previous port'},baseVersion:1}));
  localStorage.clear();
  const view=render(<Detail initial={node} onOpen={vi.fn()} onBack={vi.fn()} onChanged={vi.fn()} guard={{current:null}} onError={vi.fn()}/>);
  await waitFor(()=>expect(view.getByText('恢复草稿')).not.toBeNull());
  fireEvent.click(view.getByText('恢复草稿'));
  expect((view.getByLabelText('Markdown 编辑器') as HTMLTextAreaElement).value).toContain('previous port');
  fireEvent.click(view.getByText('保存',{exact:true}));
  await waitFor(()=>expect(cache.has(key)).toBe(false));
 });
});
