/* Service worker handler unit tests, not a browser installation/offline test. */
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const root=path.resolve(process.argv[2]||path.join(__dirname,'..'));
const src=fs.readFileSync(path.join(root,'service-worker.js'),'utf8');
const handlers={},deleted=[],puts=[],core=[];let status=200;
const cache={addAll:async xs=>core.push(...xs),match:async()=>undefined,put:async(...xs)=>puts.push(xs)};
const old=['briar-crown-v1.7.7.3-ironthorn-gate-item-inspect-hotfix','comic-vault-cache','some-other-app'];
const context={self:{addEventListener:(t,h)=>handlers[t]=h,skipWaiting:()=>{},clients:{claim:async()=>{}}},caches:{open:async()=>cache,keys:async()=>old,delete:async k=>{deleted.push(k);return true},match:async()=>undefined},fetch:async()=>new Response('fixture',{status}),URL,Response,console};
vm.runInNewContext(src,context);
(async()=>{
 let done;handlers.install({waitUntil:p=>done=p});await done;
 assert(core.includes('./assets/items/manifest.json'));console.log('PASS sw:precache-item-registry');
 handlers.activate({waitUntil:p=>done=p});await done;
 assert.deepEqual(deleted,[old[0]]);console.log('PASS sw:preserve-other-app-caches');
 status=503;handlers.fetch({request:{method:'GET',url:'https://example.test/index.html',mode:'navigate',destination:'document'},respondWith:p=>done=p});await done;await Promise.resolve();
 assert.equal(puts.length,0);console.log('PASS sw:failed-page-not-cached');
 status=200;handlers.fetch({request:{method:'GET',url:'https://example.test/index.html',mode:'navigate',destination:'document'},respondWith:p=>done=p});await done;await Promise.resolve();
 assert.equal(puts.length,1);console.log('PASS sw:successful-page-cached');
})().catch(e=>{console.error(e);process.exitCode=1});
