import {useEffect,useRef,useState} from 'react';
import {api} from './api';
import {desktop} from './desktop';
import {defaultReading,type ReadingWorkspace} from './reading';

export function useReadingWorkspace(paperId:string|null,onError:(e:unknown)=>void){
 const [state,setState]=useState<ReadingWorkspace>(defaultReading),[ready,setReady]=useState(!paperId);
 const latest=useRef<ReadingWorkspace>(defaultReading),loaded=useRef(false),pending=useRef(Promise.resolve(true)),timer=useRef<ReturnType<typeof setTimeout>|undefined>(undefined),saved=useRef('');
 const key='rh-capture-'+paperId;
 async function flush(final=false){
  if(!paperId||!loaded.current)return true;
  clearTimeout(timer.current);const value=latest.current,serial=JSON.stringify(value);
  if(serial===saved.current)return pending.current;
  pending.current=pending.current.then(async()=>{try{await api('/papers/'+paperId+'/reading-workspace',{method:'PUT',body:serial,keepalive:final});saved.current=serial;if(JSON.stringify(latest.current)===serial){localStorage.removeItem(key);await desktop?.writeCache(key,null);}return true;}catch(e){onError(new Error('阅读草稿尚未写入工作空间：'+String(e)));return false;}});
  return pending.current;
 }
 const flushRef=useRef(flush);flushRef.current=flush;
 function update(next:ReadingWorkspace){latest.current=next;setState(next);if(!paperId)return;const serial=JSON.stringify(next);try{localStorage.setItem(key,serial);}catch(e){onError(e);}void desktop?.writeCache(key,serial).catch(onError);clearTimeout(timer.current);timer.current=setTimeout(()=>void flushRef.current(),650);}
 useEffect(()=>{
  if(!paperId)return;let live=true;
  void(async()=>{try{const remote=await api<ReadingWorkspace>('/papers/'+paperId+'/reading-workspace');if(!live)return;let cached:string|null=localStorage.getItem(key);try{cached=await desktop?.readCache(key)||cached;}catch(e){onError(e);}if(!live)return;
   let value={...defaultReading,...remote};saved.current=JSON.stringify(value);
   if(cached)try{const parsed=JSON.parse(cached);if(parsed&&['note','pdf','split'].includes(parsed.mode))value={...value,...parsed};}catch{}
   latest.current=value;setState(value);loaded.current=true;setReady(true);if(JSON.stringify(value)!==saved.current)void flushRef.current();
  }catch(e){onError(e);}})();
  const leave=()=>void flushRef.current(true);window.addEventListener('pagehide',leave);
  return()=>{live=false;clearTimeout(timer.current);void flushRef.current(true);window.removeEventListener('pagehide',leave);};
 },[paperId]);
 return {state,latest,update,flush:()=>flushRef.current(),ready};
}
