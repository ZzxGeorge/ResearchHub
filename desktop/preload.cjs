const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('researchHubDesktop',Object.freeze({
 info:()=>ipcRenderer.invoke('desktop:info'),
 readCache:(key)=>ipcRenderer.invoke('desktop:cache-read',key),
 writeCache:(key,value)=>ipcRenderer.invoke('desktop:cache-write',key,value),
 chooseWorkspace:()=>ipcRenderer.invoke('desktop:choose-workspace'),
 openWorkspace:()=>ipcRenderer.invoke('desktop:open-workspace'),
 openLogs:()=>ipcRenderer.invoke('desktop:open-logs')
}));
