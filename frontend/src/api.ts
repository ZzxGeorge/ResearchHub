export async function api<T=any>(path:string,options:RequestInit={}):Promise<T>{
  const response=await fetch('/api'+path,{...options,headers:options.body instanceof FormData?options.headers:{'Content-Type':'application/json',...options.headers}});
  if(!response.ok){let detail;try{detail=(await response.json()).detail;}catch{detail=response.statusText;}throw new Error(typeof detail==='string'?detail:JSON.stringify(detail));}
  return response.json();
}
export const post=<T=any>(path:string,body:unknown)=>api<T>(path,{method:'POST',body:JSON.stringify(body)});
export async function downloadBackup(){const r=await fetch('/api/backup',{method:'POST'});if(!r.ok){throw new Error((await r.json()).detail);}download(await r.blob(),'research-hub-backup.zip');}
export function download(blob:Blob,name:string){const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
