const {test}=require('node:test');const assert=require('node:assert/strict');
const {trusted,external,bounds}=require('../policy.cjs');
test('credentials and IPC are restricted to exact loopback origin',()=>{
 assert.equal(trusted('http://127.0.0.1:456/api','http://127.0.0.1:456'),true);
 for(const url of ['http://127.0.0.1:457/api','http://127.0.0.1.evil:456/api','https://evil.example/','file:///C:/secret','javascript:alert(1)'])assert.equal(trusted(url,'http://127.0.0.1:456'),false);
});
test('external links never open executables, files, local services or unknown protocols',()=>{
 assert.equal(external('https://arxiv.org/abs/example'),true);
 for(const url of ['file:///C:/test.exe','javascript:bad','shell:AppsFolder','http://localhost:8000','http://127.0.0.1:8000'])assert.equal(external(url),false);
});
test('window bounds recover from removed monitors and clamp dimensions',()=>{
 const displays=[{workArea:{x:0,y:0,width:1920,height:1080}}];
 assert.deepEqual(bounds({x:6000,y:6000,width:1000,height:800},displays),{width:1360,height:920});
 const b=bounds({x:100,y:100,width:9999,height:9999},displays);assert.equal(b.width,1920);assert.equal(b.height,1080);
});
