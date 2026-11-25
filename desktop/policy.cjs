const {URL}=require('node:url');
function trusted(url,origin){try{return new URL(url).origin===origin;}catch{return false;}}
function external(url){try{const u=new URL(url);return ['https:','http:'].includes(u.protocol)&&!['127.0.0.1','localhost','[::1]'].includes(u.hostname);}catch{return false;}}
function bounds(saved,displays){
  if(!saved||![saved.width,saved.height].every(Number.isFinite))return {width:1360,height:920};
  const area=displays.find(({workArea:a})=>Number.isFinite(saved.x)&&Number.isFinite(saved.y)&&saved.x+100>a.x&&saved.y+100>a.y&&saved.x<a.x+a.width-100&&saved.y<a.y+a.height-100)?.workArea;
  return area?{width:Math.min(Math.max(860,saved.width),area.width),height:Math.min(Math.max(600,saved.height),area.height),x:Math.max(area.x,Math.min(saved.x,area.x+area.width-200)),y:Math.max(area.y,Math.min(saved.y,area.y+area.height-150))}:{width:1360,height:920};
}
module.exports={trusted,external,bounds};
