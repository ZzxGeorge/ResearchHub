import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {act,cleanup,fireEvent,render} from '@testing-library/react';
import {Detail} from '../src/Detail';
import {api} from '../src/api';
import type {Node} from '../src/types';
vi.mock('../src/api',()=>({api:vi.fn(),post:vi.fn(),download:vi.fn()}));
vi.mock('../src/Markdown',()=>({Markdown:({text}:{text:string})=><div>{text}</div>}));
const node:Node={id:'note-1',kind:'paper',title:'Paper',status:'to_read',tags:[],metadata:{},version:1,markdown:'Original',created_at:'2026-01-01',updated_at:'2026-01-01',relations:[],attachments:[]};
const tick=()=>act(async()=>{await vi.advanceTimersByTimeAsync(1500);});
function setup(){const guard={current:null as null|(()=>Promise<boolean>)};const onChanged=vi.fn();const view=render(<Detail initial={node} onOpen={vi.fn()} onBack={vi.fn()} onChanged={onChanged} guard={guard} onError={vi.fn()}/>);return {...view,guard,onChanged};}
beforeEach(()=>{vi.useFakeTimers();localStorage.clear();vi.mocked(api).mockImplementation(async(path)=>path==='/categories'?[]:{items:[]});});
afterEach(()=>{cleanup();vi.useRealTimers();vi.clearAllMocks();});
describe('durable note editing',()=>{
 it('serializes saves and advances optimistic versions when edited during an in-flight save',async()=>{
  let resolveFirst:(value:any)=>void=()=>{};const requests:any[]=[];
  vi.mocked(api).mockImplementation(async(path,options)=>{if(options?.method==='PUT'){requests.push(JSON.parse(String(options.body)));if(requests.length===1)return new Promise(r=>{resolveFirst=r;});return {...node,version:3};}return path==='/categories'?[]:{items:[]};});
  const view=setup();fireEvent.change(view.getByLabelText('Markdown 编辑器'),{target:{value:'First edit'}});await tick();
  expect(requests.length).toBe(1);expect(requests[0].expected_version).toBe(1);
  fireEvent.change(view.getByLabelText('Markdown 编辑器'),{target:{value:'Second edit during network request'}});await tick();expect(requests.length).toBe(1);
  await act(async()=>{resolveFirst({...node,version:2});});await tick();
  expect(requests.length).toBe(2);expect(requests[1].expected_version).toBe(2);expect(requests[1].markdown).toBe('Second edit during network request');
  expect(localStorage.getItem('rh-draft-note-1')).toBeNull();expect(await view.guard.current!()).toBe(true);
 });
 it('keeps the local draft and blocks navigation on stale revision conflicts',async()=>{
  const requests:any[]=[];vi.mocked(api).mockImplementation(async(path,options)=>{if(options?.method==='PUT'){requests.push(options);throw new Error('笔记已有更新。请重新加载后合并。');}return path==='/categories'?[]:{items:[]};});
  const view=setup();fireEvent.change(view.getByLabelText('Markdown 编辑器'),{target:{value:'My irreplaceable handwritten note'}});await tick();
  expect(localStorage.getItem('rh-draft-note-1')).toContain('My irreplaceable handwritten note');expect(await view.guard.current!()).toBe(false);await tick();expect(requests.length).toBe(1);
  expect(view.getByText('下载草稿')).not.toBeNull();
 });
});
