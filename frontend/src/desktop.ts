export interface DesktopInfo{version:string;workspace:string;logs:string;packaged:boolean}
declare global{interface Window{researchHubDesktop?:{info:()=>Promise<DesktopInfo>;readCache:(key:string)=>Promise<string|null>;writeCache:(key:string,value:string|null)=>Promise<void>;chooseWorkspace:()=>Promise<boolean>;openWorkspace:()=>Promise<string>;openLogs:()=>Promise<string>}}}
export const desktop=window.researchHubDesktop;
