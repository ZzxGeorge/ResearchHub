const {app,BrowserWindow,dialog,ipcMain,shell,screen,Menu,session}=require('electron');
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const crypto=require('node:crypto');
const {trusted,external,bounds}=require('./policy.cjs');
let win,child,origin='',token='',workspace='',quitting=false,stopping=false;
const arg=(key)=>{const i=process.argv.indexOf(key);return i>=0?process.argv[i+1]:undefined;};
// QA flags are available in packaged builds for isolated, reproducible acceptance only.
if(arg('--profile-dir'))app.setPath('userData',path.resolve(arg('--profile-dir')));
const profile=app.getPath('userData'),configPath=path.join(profile,'desktop.json');
fs.mkdirSync(profile,{recursive:true});
const logs=path.join(profile,'logs');fs.mkdirSync(logs,{recursive:true});
const logfile=path.join(logs,'desktop.log');
function log(value){fs.appendFileSync(logfile,new Date().toISOString()+' '+value+'\n');}
function readConfig(){try{return JSON.parse(fs.readFileSync(configPath,'utf8'));}catch{return {};}}
function saveConfig(patch){const temp=configPath+'.tmp';fs.writeFileSync(temp,JSON.stringify({...readConfig(),...patch},null,2));fs.renameSync(temp,configPath);}
async function stopBackend(){
 const owned=child;child=undefined;if(!owned||owned.exitCode!==null)return;
 await new Promise(resolve=>{const timer=setTimeout(()=>{owned.kill();resolve();},7000);owned.once('exit',()=>{clearTimeout(timer);resolve();});owned.stdin.end('stop\n');});
}
async function startBackend(selected){
 token=crypto.randomBytes(32).toString('hex');const instance=crypto.randomUUID();
 const executable=app.isPackaged?path.join(process.resourcesPath,'backend','ResearchHubBackend.exe'):path.join(__dirname,'..','.venv','Scripts','python.exe');
 const args=app.isPackaged?[]:[path.join(__dirname,'..','backend','desktop_entry.py')];
 const env={...process.env,RESEARCH_HUB_WORKSPACE:selected,RESEARCH_HUB_DESKTOP_TOKEN:token,RESEARCH_HUB_INSTANCE:instance,RESEARCH_HUB_LOG_DIR:logs};
 // Never inherit Electron's node-mode switch into a bundled backend.
 delete env.ELECTRON_RUN_AS_NODE;
 const owned=spawn(executable,args,{env,windowsHide:true,stdio:['pipe','pipe','pipe'],cwd:path.dirname(executable)});child=owned;
 owned.stderr.on('data',data=>log(data.toString().trim()));
 const ready=await new Promise((resolve,reject)=>{
   const timeout=setTimeout(()=>reject(new Error('后端启动超时，请查看应用日志。')),60000);
   let buffer='';
   owned.once('error',e=>{clearTimeout(timeout);reject(e);});
   owned.once('exit',code=>{clearTimeout(timeout);reject(new Error('后端提前退出（'+code+'），可能已有服务占用此工作空间。'));});
   owned.stdout.on('data',data=>{buffer+=data.toString();let idx;while((idx=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,idx);buffer=buffer.slice(idx+1);try{const message=JSON.parse(line);if(message.event==='ready'&&message.instance===instance){clearTimeout(timeout);resolve(message);}}catch{log(line);}}});
 });
 origin='http://127.0.0.1:'+ready.port;
 const health=await fetch(origin+'/api/health',{headers:{'X-Research-Hub-Token':token},signal:AbortSignal.timeout(10000)});
 const body=await health.json();if(!health.ok||body.instance!==instance||body.version!==app.getVersion())throw new Error('后端身份校验失败。');
 owned.on('exit',()=>{if(!quitting&&child===owned){log('Backend exited unexpectedly');dialog.showErrorBox('Research Hub 服务中断','请重新启动应用。数据保留在：'+workspace+'\n日志目录：'+logs);win?.destroy();app.quit();}});
}
function verifyIPC(event){if(!win||event.sender!==win.webContents||event.senderFrame!==win.webContents.mainFrame||!trusted(event.senderFrame.url,origin))throw new Error('Untrusted IPC sender');}
async function openWindow(){
 const config=readConfig();const partition='persist:researchhub-'+crypto.createHash('sha256').update(workspace.toLowerCase()).digest('hex').slice(0,20);
 const ses=session.fromPartition(partition);ses.setPermissionRequestHandler((wc,permission,callback,details)=>callback(permission==='fullscreen'&&wc===win?.webContents&&trusted(details.requestingUrl,origin)));ses.setPermissionCheckHandler((wc,permission,requestingOrigin)=>permission==='fullscreen'&&wc===win?.webContents&&requestingOrigin===origin);
 win=new BrowserWindow({...bounds(config.bounds,screen.getAllDisplays()),show:false,minWidth:860,minHeight:600,title:'Research Hub',icon:path.join(__dirname,'assets','icon.ico'),backgroundColor:'#141b19',webPreferences:{preload:path.join(__dirname,'preload.cjs'),contextIsolation:true,nodeIntegration:false,sandbox:true,webSecurity:true,partition}});
 ses.webRequest.onBeforeSendHeaders((details,callback)=>{const headers={...details.requestHeaders};delete headers['X-Research-Hub-Token'];if(trusted(details.url,origin)&&details.webContentsId===win?.webContents.id)headers['X-Research-Hub-Token']=token;callback({requestHeaders:headers});});
 ses.webRequest.onHeadersReceived((details,callback)=>{const headers={...details.responseHeaders};if(trusted(details.url,origin))headers['Content-Security-Policy']=["default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; frame-src 'none'; base-uri 'none'; form-action 'self'"];callback({responseHeaders:headers});});
 const externalLink=(url)=>{if(external(url))void shell.openExternal(url);};
 win.webContents.setWindowOpenHandler(({url})=>{if(trusted(url,origin)){void win.webContents.downloadURL(url);}else externalLink(url);return {action:'deny'};});
 win.webContents.on('will-navigate',(event,url)=>{if(!trusted(url,origin)){event.preventDefault();externalLink(url);}});
 win.webContents.on('will-attach-webview',event=>event.preventDefault());
 win.webContents.on('will-prevent-unload',event=>{const choice=dialog.showMessageBoxSync(win,{type:'warning',buttons:['留在应用中','退出并保留浏览器草稿'],defaultId:0,cancelId:0,message:'当前笔记尚未保存。建议先完成保存或下载草稿。'});if(choice===1)event.preventDefault();});
 win.on('close',()=>{if(!win.isDestroyed())saveConfig({bounds:win.getNormalBounds(),maximized:win.isMaximized()});});
 win.once('ready-to-show',()=>{if(config.maximized)win.maximize();win.show();});
 await win.loadURL(origin+'/');
}
if(!app.requestSingleInstanceLock()){app.quit();}else{
 app.on('second-instance',()=>{if(win){if(win.isMinimized())win.restore();win.show();win.focus();}});
 app.whenReady().then(async()=>{
  try{
   workspace=path.resolve(arg('--workspace')||process.env.RESEARCH_HUB_WORKSPACE||readConfig().workspace||path.join(os.homedir(),'.research-hub','workspace'));
   if(app.isPackaged&&(workspace===process.resourcesPath||workspace.startsWith(path.dirname(app.getPath('exe'))+path.sep)))throw new Error('工作空间不能位于安装目录中。');
   await startBackend(workspace);saveConfig({workspace});
   function cacheFile(key){if(typeof key!=='string'||!/^rh-(theme|(?:draft|capture)-[a-f0-9-]{36})$/.test(key))throw new Error('Invalid UI cache key');const scope=crypto.createHash('sha256').update(workspace.toLowerCase()).digest('hex');const directory=path.join(profile,'ui-cache',scope);fs.mkdirSync(directory,{recursive:true});return path.join(directory,key+'.json');}
   ipcMain.handle('desktop:cache-read',(event,key)=>{verifyIPC(event);const file=cacheFile(key);return fs.existsSync(file)?fs.readFileSync(file,'utf8'):null;});
   ipcMain.handle('desktop:cache-write',(event,key,value)=>{verifyIPC(event);const file=cacheFile(key);if(value===null){if(fs.existsSync(file))fs.unlinkSync(file);return;}if(typeof value!=='string'||value.length>4000000)throw new Error('UI cache value too large');if(key==='rh-theme'&&!['light','dark'].includes(value))throw new Error('Invalid theme');fs.writeFileSync(file+'.tmp',value,'utf8');fs.renameSync(file+'.tmp',file);});
   ipcMain.handle('desktop:info',event=>{verifyIPC(event);return {version:app.getVersion(),workspace,logs,packaged:app.isPackaged};});
   ipcMain.handle('desktop:open-workspace',event=>{verifyIPC(event);return shell.openPath(workspace);});
   ipcMain.handle('desktop:open-logs',event=>{verifyIPC(event);return shell.openPath(logs);});
   ipcMain.handle('desktop:choose-workspace',async event=>{
    verifyIPC(event);const result=await dialog.showOpenDialog(win,{title:'选择已有或新的科研工作空间',properties:['openDirectory','createDirectory']});if(result.canceled)return false;
    const selected=path.resolve(result.filePaths[0]);const installation=path.dirname(app.getPath('exe'));
    if(app.isPackaged&&(selected===installation||selected.startsWith(installation+path.sep)))throw new Error('不能选择安装目录。');
    const answer=await dialog.showMessageBox(win,{type:'question',buttons:['取消','切换并重启'],defaultId:0,cancelId:0,message:'已保存的资料将留在原目录。新工作空间：\n'+selected});if(answer.response!==1)return false;
    saveConfig({workspace:selected});
    const restartArgs=process.argv.slice(1).filter((v,i,a)=>v!=='--workspace'&&a[i-1]!=='--workspace');
    app.relaunch({args:[...restartArgs,'--workspace',selected]});win.close();return true;
   });
   Menu.setApplicationMenu(Menu.buildFromTemplate([{label:'Research Hub',submenu:[{role:'quit'}]},{label:'编辑',submenu:[{role:'undo'},{role:'redo'},{type:'separator'},{role:'cut'},{role:'copy'},{role:'paste'},{role:'selectAll'}]},{label:'视图',submenu:[{role:'togglefullscreen'},{role:'resetZoom'},{role:'zoomIn'},{role:'zoomOut'}]}]));
   await openWindow();log('Application ready (v'+app.getVersion()+')');
  }catch(e){log(String(e.stack||e));await stopBackend();dialog.showErrorBox('Research Hub 无法启动',e.message+'\n原资料不会被空数据库替换。日志：'+logfile);app.quit();}
 });
 app.on('window-all-closed',()=>app.quit());
 app.on('before-quit',event=>{if(!stopping&&child){event.preventDefault();if(win&&!win.isDestroyed()){win.close();if(!win.isDestroyed())return;}stopping=true;quitting=true;void stopBackend().finally(()=>app.quit());}});
}
