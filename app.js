let theme=localStorage.getItem('uai_theme')||'light',think=false,search=false,busy=false,hist=[],sideOpen=window.innerWidth>768,prevModel=null;
const _isServer=location.protocol!=='file:';
function _dateStr(){const t=new Date();return t.getFullYear()+'年'+(t.getMonth()+1)+'月'+t.getDate()+'日'}
function _recordMsg(r,c){addMsg(r,c);hist.push({role:r,content:c});CM.appendMessage(r,c)}
const REALTIME_RE=new RegExp(['最新','实时','今天','现在','新闻','价格','天气','开奖','彩票','快乐8','大乐透','双色球','比分','赛程','股价','股票','汇率','黄金','白银','比特币','以太坊','期货','原油','石油','铜价','大豆','外汇','利率','考试','高考','AI','大模型','DeepSeek','Claude','GPT','显卡','CPU','内存','装机','直播','附近','路况','限行','预警','地震','多少钱','性价比','评测','买车','落地价','报价','配置','保养','保险','油耗','二手','回收价','手机','iPhone','华为','小米','OPPO','vivo','三星','折叠屏'].join('|'));
function _isRealtime(txt){return REALTIME_RE.test(txt)}
function tglTheme(){theme=theme=='light'?'dark':'light';document.body.className=theme;localStorage.setItem('uai_theme',theme);document.getElementById('hl-theme').href=theme=='dark'?'https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github-dark.min.css':'https://cdn.jsdelivr.net/gh/highlightjs/cdn-release@11.9.0/build/styles/github.min.css'}
document.body.className=theme;
function tglSide(){sideOpen=!sideOpen;document.getElementById('side').classList.toggle('open',sideOpen)}
function openSet(){document.getElementById('modal').classList.add('show')}
function closeSet(){document.getElementById('modal').classList.remove('show')}
function saveSet(){const c={apiKey:document.getElementById('apikey').value,model:document.getElementById('model').value,think,search,debug:document.getElementById('debug-toggle').checked};localStorage.setItem('uai_cfg',JSON.stringify(c));closeSet();updateModelBadge();stat('已保存')}
function toggleDebug(){const p=document.getElementById('debug-panel');const on=document.getElementById('debug-toggle').checked;p.style.display=on?'block':'none';localStorage.setItem('uai_debug',on?'1':'0')}
function tglThink(){think=!think;document.getElementById('c-think').classList.toggle('on',think);const sel=document.getElementById('model');if(think){prevModel=sel.value;sel.value='deepseek-v4-pro'}else if(prevModel){sel.value=prevModel;prevModel=null}saveCfg()}
function tglSearch(){search=!search;document.getElementById('c-search').classList.toggle('on',search);if(search&&location.protocol=='file:')stat('联网搜索需服务器模式','var(--dng)');saveCfg()}
function loadCfg(){try{const c=JSON.parse(localStorage.getItem('uai_cfg')||'{}');if(c.apiKey)document.getElementById('apikey').value=c.apiKey;if(c.model)document.getElementById('model').value=c.model;if(c.think){think=true;document.getElementById('c-think').classList.add('on')}if(c.search){search=true;document.getElementById('c-search').classList.add('on')}}catch(e){}}
function saveCfg(){localStorage.setItem('uai_cfg',JSON.stringify({apiKey:document.getElementById('apikey').value,model:document.getElementById('model').value,think,search}))}
loadCfg();if(localStorage.getItem('uai_debug')==='1'){document.getElementById('debug-toggle').checked=true;document.getElementById('debug-panel').style.display='block'}
function stat(t,c){const e=document.getElementById('status-text');if(e){e.textContent=t;e.style.color=c||''}}
function updateModelBadge(){const m=document.getElementById('model').value;const b=document.getElementById('model-badge');if(!b)return;const isLocal=m.indexOf(':')!==-1;b.textContent=m;b.style.cssText='font-size:10px;padding:2px 8px;border-radius:10px;margin-right:8px;font-weight:600;'+(isLocal?'background:#4a9060;color:#fff':'background:var(--acc);color:#fff')}
let _dlogMsgs=[];
function _dlog(tag,msg){const ts=new Date().toLocaleTimeString();const entry=ts+' ['+tag+'] '+msg;_dlogMsgs.push(entry);if(_dlogMsgs.length>20)_dlogMsgs.shift();try{const el=document.getElementById('debug-log');if(el)el.textContent=_dlogMsgs.join('\n')}catch(e){}}
function esc(s){s=String(s==null?'':s);const m={'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};return s.replace(/[&<>"']/g,c=>m[c])}
function scrollChat(){const c=document.getElementById('chat');c.scrollTop=c.scrollHeight}
function _cleanToolMarkers(t){return t.replace(/\[TOOL:\w+[^\]]*\]/g,'').replace(/\n{3,}/g,'\n\n').trim()}
// ====== Unified Message Renderer ======
function renderMessage(rawMarkdown){
  _dlog('RENDER',(rawMarkdown||'').length+'chars marked='+(typeof marked!=='undefined')+' katex='+(typeof katex!=='undefined'));
  if(!rawMarkdown)return'';
  if(typeof marked==='undefined'){
    _dlog('RENDER','FALLBACK');
    let h=esc(rawMarkdown);
    h=h.replace(/```(\w*)\n?([\s\S]*?)```/g,'<pre><code>$2</code></pre>');
    h=h.replace(/`([^`]+)`/g,'<code>$1</code>');
    h=h.replace(/^### (.+)$/gm,'<h3>$1</h3>');h=h.replace(/^## (.+)$/gm,'<h2>$1</h2>');h=h.replace(/^# (.+)$/gm,'<h1>$1</h1>');
    h=h.replace(/\*\*(.+?)\*\*/g,'<b>$1</b>');h=h.replace(/\*(.+?)\*/g,'<i>$1</i>');
    h=h.replace(/\n\n/g,'<br><br>');h=h.replace(/\n/g,'<br>');
    return h;
  }
  const mathBlocks=[],mathInlines=[];
  let h=rawMarkdown;
  h=h.replace(/\\\[([\s\S]*?)\\\]/g,(_,m)=>{mathBlocks.push(m.trim());return'\x01MB'+(mathBlocks.length-1)+'\x01'});
  h=h.replace(/\\\(([\s\S]*?)\\\)/g,(_,m)=>{mathInlines.push(m.trim());return'\x01MI'+(mathInlines.length-1)+'\x01'});
  try{h=marked.parse(h,{breaks:true,gfm:true});_dlog('MARKED','OK:'+h.slice(0,80))}catch(e){h='<p>'+esc(rawMarkdown)+'</p>';_dlog('MARKED','FAIL:'+e.message)}
  _dlog('KATEX','blocks='+mathBlocks.length+' inlines='+mathInlines.length);
  h=h.replace(/\x01MB(\d+)\x01/g,(_,i)=>{
    try{return katex.renderToString(mathBlocks[+i],{displayMode:true,throwOnError:false})}catch(e){return'<pre>'+esc(mathBlocks[+i])+'</pre>'}
  });
  h=h.replace(/\x01MI(\d+)\x01/g,(_,i)=>{
    try{return katex.renderToString(mathInlines[+i],{displayMode:false,throwOnError:false})}catch(e){return'<code>'+esc(mathInlines[+i])+'</code>'}
  });
  const tmp=document.createElement('div');tmp.innerHTML=h;
  tmp.querySelectorAll('pre code').forEach(block=>{
    const lang=(block.className||'').replace('language-','')||'plaintext';
    try{const r=hljs.highlight(block.textContent,{language:lang,ignoreIllegals:true});block.innerHTML=r.value;block.className+=' hljs'}catch(e){}
    const pre=block.parentElement;
    if(pre&&pre.tagName==='PRE'&&!pre.querySelector('.copy-btn')){
      pre.style.position='relative';
      const btn=document.createElement('button');
      btn.className='copy-btn';btn.textContent='复制';btn.style.cssText='position:absolute;top:4px;right:8px;z-index:1;padding:2px 8px;border-radius:4px;border:1px solid var(--bdr);background:var(--sfc);color:var(--txd);cursor:pointer;font-size:10px';
      btn.onclick=function(){cp(btn)};pre.appendChild(btn);
    }
  });
  return tmp.innerHTML;
}
function md(text){return renderMessage(text)}
function cp(btn){const pre=btn.closest('pre');const code=pre?pre.querySelector('code'):null;const text=code?code.textContent:'';if(!text)return;navigator.clipboard.writeText(text).then(()=>{btn.textContent='已复制!';setTimeout(()=>btn.textContent='复制',1500)}).catch(()=>{const ta=document.createElement('textarea');ta.value=text;ta.style.cssText='position:fixed;opacity:0';document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);btn.textContent='已复制!';setTimeout(()=>btn.textContent='复制',1500)})}
function show(){document.getElementById('welcome').classList.add('hidden');document.getElementById('chat').classList.add('on')}
function hide(){document.getElementById('welcome').classList.remove('hidden');document.getElementById('chat').classList.remove('on');document.getElementById('chat').innerHTML=''}
function addMsg(r,c){_dlog('ADD_MSG','role='+r+' len='+(c||'').length);show();const isAI=r==='ai'||r==='assistant';const d=document.createElement('div');d.className='msg '+(r==='user'?'user':'ai');const avatar=isAI?'🤖':'👤';const body=isAI?renderMessage(c):'<p>'+esc(c)+'</p>';d.innerHTML='<div class="av">'+avatar+'</div><div class="b">'+body+'</div>';document.getElementById('chat').appendChild(d);scrollChat()}
function clrChat(){CM.clearCurrent();hide();hist=[];}
function loadChats(){CM._load();renderChats();}
function renderChats(){
  const el=document.getElementById('chat-list');
  const chats=CM.getAllConversations();
  if(!chats.length){el.innerHTML='<div style="padding:24px;text-align:center;font-size:12px;color:var(--txd)">暂无历史对话</div>';return}
  el.innerHTML=chats.map(c=>'<div class="ci" onclick="loadChat(\''+c.id+'\')"><span style="font-size:14px">💬</span><span class="t">'+esc(c.title||'新对话')+'</span><span class="x" onclick="event.stopPropagation();delChat(\''+c.id+'\')">×</span></div>').join('');
}
function loadChat(id){const msgs=CM.loadConversation(id);if(!msgs)return;hist=msgs;show();document.getElementById('chat').innerHTML='';msgs.forEach(m=>addMsg(m.role,m.content));stat('已加载');if(window.innerWidth<=768)tglSide()}
function delChat(id){if(!confirm('确定删除？'))return;CM.deleteConversation(id);if(!CM._currentId){hide();hist=[]}renderChats()}
function newChat(){CM.newConversation();hide();hist=[];renderChats();stat('已新建对话');document.getElementById(window.innerWidth<=768?'winput':'input').focus()}
function autoSave(){const cur=CM.getCurrentConversation();if(cur&&hist.length){cur.messages=JSON.parse(JSON.stringify(hist));cur.updatedAt=Date.now();CM._save();CM._recoverySave()}}
function autoRestore(){_dlog('RESTORE','start');const saved=CM.autoRestore();if(saved){_dlog('RESTORE','found id='+saved.id+' msgs='+saved.messages.length);hist=JSON.parse(JSON.stringify(saved.messages));if(saved.messages.length){show();document.getElementById('chat').innerHTML='';saved.messages.forEach(m=>{_dlog('RESTORE','replay '+m.role+' len='+(m.content||'').length);addMsg(m.role,m.content)})}stat('已恢复: '+saved.title);renderChats()}else{_dlog('RESTORE','nothing to restore')}}

// ============ TOKEN OPT: Response Cache (24h TTL) ============
// Saves ~100% tokens for repeated queries
function _cacheKey(txt){let h=0;for(let i=0;i<txt.length;i++){h=((h<<5)-h)+txt.charCodeAt(i);h|=0}return 'uai_cache_'+h.toString(36)}
function _cacheGet(txt){
  try{const e=JSON.parse(localStorage.getItem(_cacheKey(txt))||'null');if(e&&Date.now()-e.ts<86400000)return e.val}catch(e){}
  return null;
}
function _cacheSet(txt,val){try{const o=JSON.stringify({ts:Date.now(),val});if(o.length<50000)localStorage.setItem(_cacheKey(txt),o)}catch(e){}}

// ============ TOKEN OPT: Zero-Token Mode (local handlers) ============
// Saves ~100% tokens for simple queries that don't need LLM
function _zeroToken(txt){
  const t=txt.trim().toLowerCase();
  // Greetings
  if(/^(你好|hi|hello|hey|嗨|早|晚上好|下午好)[\s!！。.]*$/.test(t))return '你好！有什么可以帮你的？';
  if(/^(谢谢|thanks|thank|3q|thx).*/.test(t))return '不客气！';
  // Time/date
  if(/^(现在几点|几点了|当前时间|现在时间|今天日期|今天几号|今天星期几|日期)[\s?？!！。.]*$/.test(t)){
    const now=new Date();
    return '现在是 **'+_dateStr()+' '+now.getHours()+':'+String(now.getMinutes()).padStart(2,'0')+':'+String(now.getSeconds()).padStart(2,'0')+'**（星期'+'日一二三四五六'[now.getDay()]+'）';
  }
  // Help commands
  if(/^(帮助|help|\/help|功能|命令|使用说明)[\s?？!！。.]*$/.test(t)){
    return '**USB-AI 帮助**\n\n- 直接输入问题，AI 会回答\n- `/search 关键词` 内置网页搜索\n- 🌐 开启联网搜索：AI 自动检索实时信息\n- 🧠 深度思考模式用于复杂推理\n- ⚙ 设置中配置 API Key 和模型\n- ＋新建：开启新对话\n- 🗑 清空当前对话';
  }
  // Simple math (no LLM needed)
  if(/^[\d\s+\-*/().%^]+$/.test(t)&&/[\d]/.test(t)&&t.length<80){
    try{const r=Function('"use strict";return ('+t+')')();if(typeof r==='number'&&isFinite(r))return '**'+t+' = '+r+'**'}catch(e){}
  }
  // System info (zero token)
  if(/^(系统|system|version|版本|状态|status)[\s?？!！。.]*$/.test(t)){
    return '**USB-AI v4.1**\n\n模型: '+(document.getElementById('model').value)+'\n搜索: '+(search?'开':'关')+'\n主题: '+(theme==='dark'?'暗色':'亮色')+'\n在线: '+(location.protocol!=='file:');
  }
  // IP / network
  if(/^(我的ip|ip地址|网络状态|我的网络)[\s?？!！。.]*$/.test(t)){
    return '此功能需联网模式。当前: '+(location.protocol==='file:'?'直连模式（无法获取网络信息）':'服务器模式');
  }
  return null; // Needs LLM
}

// ============ Trusted URL Directory ============
function _trustedSources(txt){
  const t=txt.toLowerCase();const s=[];
  if(/黄金|金价|白银|铂金|钯金|贵金属/.test(t))s.push('上海金交所: https://www.sge.com.cn','Kitco: https://www.kitco.com');
  if(/股票|股价|A股|港股|美股|上证|深证|纳斯达克|恒生|创业板|科创板/.test(t))s.push('东方财富: https://www.eastmoney.com','雪球: https://xueqiu.com','同花顺: https://www.10jqka.com.cn');
  if(/期货|原油|铜价|铝价|螺纹钢|铁矿石|大豆|玉米|棉花/.test(t))s.push('上海期货交易所: https://www.shfe.com.cn','生意社: https://www.100ppi.com','金十数据: https://www.jin10.com');
  if(/汇率|外汇|美元|欧元|日元|英镑|人民币/.test(t))s.push('中国银行外汇牌价: https://www.boc.cn/sourcedb/whpj','XE: https://www.xe.com');
  if(/比特币|以太坊|加密货币|区块链|狗狗币/.test(t))s.push('CoinMarketCap: https://coinmarketcap.com','币安: https://www.binance.com');
  if(/天气|气温|下雨|台风|雾霾|空气质量/.test(t))s.push('中央气象台: http://www.nmc.cn','中国天气网: http://www.weather.com.cn');
  if(/彩票|开奖|快乐8|大乐透|双色球|福彩|体彩/.test(t))s.push('彩宝网: https://www.00038.cn','中国福彩网: https://www.cwl.gov.cn');
  if(/比分|赛程|积分|排名|NBA|英超|欧冠|中超|世界杯|欧洲杯/.test(t))s.push('懂球帝: https://www.dongqiudi.com','直播吧: https://www.zhibo8.cc');
  if(/新闻|头条|热点|国际|快讯/.test(t))s.push('路透社: https://www.reuters.com','BBC中文: https://www.bbc.com/zhongwen','环球网: https://www.huanqiu.com');
  if(/AI|人工智能|大模型|GPT|Claude|DeepSeek|机器学习/.test(t))s.push('机器之心: https://www.jiqizhixin.com','Hugging Face: https://huggingface.co','ArXiv: https://arxiv.org');
  if(/考试|高考|考研|公考|雅思|托福|四六级|教资|法考|CPA/.test(t))s.push('中国教育考试网: https://www.neea.edu.cn','研招网: https://yz.chsi.com.cn');
  if(/CPU|显卡|内存|主板|SSD|装机|笔记本|手机|价格|性价比/.test(t))s.push('什么值得买: https://www.smzdm.com','京东: https://www.jd.com','中关村在线: https://www.zol.com.cn');
  if(/代码|编程|报错|bug|github|git clone|API|框架/.test(t))s.push('GitHub: https://github.com','Stack Overflow: https://stackoverflow.com','MDN: https://developer.mozilla.org');
  if(/汽车|买车|SUV|轿车|新能源|落地价|报价|配置|保养|保险|油耗|二手|回收|置换/.test(t))s.push('汽车之家: https://www.autohome.com.cn','懂车帝: https://www.dongchedi.com','易车: https://www.yiche.com','瓜子二手车: https://www.guazi.com');
  if(/手机|iPhone|华为|小米|OPPO|vivo|三星|折叠屏|旗舰机|千元机|手机回收/.test(t))s.push('中关村在线: https://www.zol.com.cn','京东手机: https://mobile.jd.com','什么值得买: https://www.smzdm.com','爱回收: https://www.aihuishou.com');
  if(/自驾|路线|攻略|景点|露营地|地图|导航|酒店/.test(t))s.push('高德地图: https://www.amap.com','马蜂窝: https://www.mafengwo.cn');
  return s;
}

// ============ TOKEN OPT: Input Classifier ============
// Routes: local | llm | search | command
function _classify(txt){
  const t=txt.trim();
  // Local: greetings, time, help, simple math, system info
  if(/^(你好|hi|hello|hey|嗨|早|晚上好|下午好|谢谢|thanks|thank|3q)[\s!！。.]*$/i.test(t))return'local';
  if(/^(现在几点|几点了|当前时间|今天日期|今天几号|日期|时间)[\s?？!！。.]*$/.test(t))return'local';
  if(/^(帮助|help|\/help|功能|命令|使用说明)[\s?？!！。.]*$/.test(t))return'local';
  if(/^(系统|system|version|版本|状态|status)[\s?？!！。.]*$/.test(t))return'local';
  if(/^(我的ip|ip地址|网络状态)[\s?？!！。.]*$/.test(t))return'local';
  if(/^[\d\s+\-*/().%^]+$/.test(t)&&/[\d]/.test(t)&&t.length<80)return'local';
  // Realtime queries: force search even if toggle is off
  if(_isRealtime(t))return location.protocol!=='file:'?'search':'llm';
  // User-triggered search: respect toggle
  if(needSearch(t))return search?'search':'llm';
  return'llm';
}

// ============ TOKEN OPT: History Compression ============
// Keeps last 8 messages + summary of older ones. Saves ~60% tokens.
const MAX_HIST=8;
function _compressHistory(){
  if(hist.length<=MAX_HIST)return hist;
  const recent=hist.slice(-MAX_HIST);
  // Generate summary of older messages
  let summary='[对话摘要] ';
  const older=hist.slice(0,-MAX_HIST);
  const userMsgs=older.filter(m=>m.role==='user').map(m=>m.content.slice(0,80));
  if(userMsgs.length){summary+='用户之前问过: '+userMsgs.join('; ')+'。'}
  summary+='以上为历史摘要，请结合最近消息理解上下文。';
  // Insert summary as system-like note at the beginning of recent
  return [{role:'user',content:summary},...recent];
}

// ============ TOKEN OPT: Token Estimator ============
function _estTokens(text){
  // Closer to real: Chinese ~1.5 tokens/char, English ~0.3 tokens/char, rest ~1
  let cn=0,en=0,other=0;
  const s=String(text||'');
  for(const c of s){
    if(/[一-鿿]/.test(c))cn++;
    else if(/[a-zA-Z]/.test(c))en++;
    else other++;
  }
  return Math.ceil(cn*1.2+en*0.3+other*1);
}

// ============ Smart Search Gate ============
function needSearch(txt){
  const triggers=['搜索','查一下','联网','最新','实时','今天','现在','新闻','官网','价格','天气',
    '开奖','彩票','快乐8','大乐透','双色球','比分','赛程','排名','股价','股票','汇率','黄金','比特币',
    '直播','在哪','多少钱','怎么去','怎么走','附近','电话','地址',
    '自驾','路线','攻略','露营地','景点','门票','路况','限行','加油站',
    '故障','报错','怎么修','怎么配','教程','安装','配置','部署','战争','冲突','打仗','开战','袭击','军事','导弹','制裁','爆发','局势','撤军','入侵','空袭','选举','当选','总统','上任','下台','政策','法案','抗议','罢工','政变','最近','目前','发生','事件','内幕','真相','现状','动态','进展','什么情况'];
  return triggers.some(k=>txt.includes(k));
}
// Intent Router
function classify(txt){if(/彩票|开奖|号码|快乐8|大乐透|双色球|排列|福彩|体彩|中奖/.test(txt))return'lottery';if(/天气|股价|股票|汇率|新闻|最新|今天|现在|实时|比分|赛程|比赛|世界杯|欧冠|NBA/.test(txt))return'realtime';return'general';}
function apiUrl(){return location.protocol=='file:'?'https://api.deepseek.com/v1/chat/completions':'/api/deepseek'}
function streamUrl(){return location.protocol=='file:'?null:'/api/deepseek/stream'}
function apiHd(k){return location.protocol=='file:'?{'Content-Type':'application/json',Authorization:'Bearer '+k}:{'Content-Type':'application/json','X-API-Key':k}}

// ============ Core Send Flow (optimized) ============
async function doSend(txt){
  if(busy)return;const mdName=document.getElementById('model').value;const key=document.getElementById('apikey').value.trim();
  if(!key&&mdName.indexOf(':')===-1){stat('请先设置 API Key','var(--dng)');openSet();return}

  // Step 0: Classify intent
  const route=_classify(txt);_dlog('ROUTE',route);

  // Step 1: Zero-token local response
  if(route==='local'){
    const local=_zeroToken(txt);
    if(local){addMsg('user',txt);hist.push({role:'user',content:txt});CM.appendMessage('user',txt);addMsg('assistant',local);hist.push({role:'assistant',content:local});CM.appendMessage('assistant',local);autoSave();stat('本地');return}
  }

  // Step 2: Cache lookup
  const cached=_cacheGet(txt);
  if(cached&&!search){addMsg('user',txt);hist.push({role:'user',content:txt});CM.appendMessage('user',txt);addMsg('assistant',cached);hist.push({role:'assistant',content:cached});CM.appendMessage('assistant',cached);autoSave();stat('缓存命中');_dlog('CACHE','hit');return}

  busy=true;document.getElementById('send').disabled=true;stat('处理中…');
  let bb=null,tw=null;
  try{
    addMsg('user',txt);hist.push({role:'user',content:txt});
    CM.appendMessage('user',txt);
    let rag='';
    const doSearch=route==='search'&&location.protocol!=='file:';_dlog('SEARCH',doSearch?'ON':'SKIP');
    if(doSearch){
      try{const ac=new AbortController();const t=setTimeout(()=>ac.abort(),15000);const r=await fetch('/api/rag',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:txt,num:8,fetch:5,maxChars:6000}),signal:ac.signal});clearTimeout(t);if(r.ok){const d=await r.json();rag=d.context||'';_dlog('RAG','ctx='+rag.length+'chars src='+(d.sources||[]).length+' engines='+(d.engines||[]).join(','));stat('搜索完成 · '+(d.searchResults||[]).length+'条'+(rag.length>50?' ✓':' ⚠'))}else{_dlog('RAG','HTTP '+r.status)}}catch(e){const em=e.name==='AbortError'?'搜索超时':e.message;_dlog('RAG','fail: '+em);stat('搜索失败: '+em)}
    }
    const today=new Date();const ds=today.getFullYear()+'年'+(today.getMonth()+1)+'月'+today.getDate()+'日';
    // Compact system prompt (~120 chars avg, saved ~40% from old ~300)
    let sp='今天是'+ds+'。';
    let intent=classify(txt);
    if(location.protocol!=='file:'){try{const r=await fetch('/api/classify',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query:txt}),signal:AbortSignal.timeout(2000)});if(r.ok){const d=await r.json();if(d.intent)intent=d.intent}}catch(e){}}
    if(rag){sp+='\n\n以下是已经为你搜索到的实时数据。⚠️铁律：你绝对不要说"我无法联网/无法获取实时数据/没有搜索结果"——搜索已完成，数据在下面。你必须基于这些数据直接回答。\n⚠️禁止批评用户的用词或术语——即便你觉得表述不准确，也要理解意图后回答，不可说教。\n\n'+rag}
    else if(doSearch){const urls=_trustedSources(txt);sp+='\n\n（搜索未获取数据。⚠️禁止说教用户"这个表述存在误导"或"你应该查权威来源"——理解用户意图比纠正用词更重要。\n用你的知识回答核心问题。如果确实超出知识范围，用 [SEARCH:改写后的查询词] 换一个角度搜索。'+(urls.length?'可信网站：\n'+urls.join('\n'):'')+'）'}
    else{sp+='\n\n你是全能顾问，风格专业犀利有幽默感。\n你的知识截止于2025年7月，今天已是'+ds+'。\n⚠️铁律1：当用户问2025年7月后的时事/战争/选举/政策/灾难/名人动向/科技发布——必须第一行写 [SEARCH:关键词] 主动搜索，不得用"我的知识截止于XX"或"你告诉我"推给用户。\n⚠️铁律2：永远不要说"你这个表述存在误导"或"你应该去查权威新闻源"——理解用户意图，用你的知识或搜索结果直接回答核心问题。用户不是来上术语课的。时效性=可信度。\n你有搜索工具：[SEARCH:查询关键词] 系统自动搜索。搜索无结果时，换关键词重搜，不要放弃。\n⚠️禁止"我无法联网/无法获取实时数据/我搜索不到"——工具在你手里，搜不到就换词重搜。\n知识覆盖：高中全科、计算机/网络、电竞/直播/二次元、民间俚语/方言梗、自驾游/路线。对历史/未来/科技/人文/宗教好奇但务实。理解当代社会压力，接地气不说道。规则：模糊问题先确认意图；不编造网址/人名/电话；简洁、少用"您"、拒绝客服体。'}
    // Compress history to last 8 messages (~saves 60% tokens)
    const msgs=[{role:'system',content:sp},..._compressHistory()];
    const estTotal=_estTokens(sp)+_estTokens(msgs.slice(1).map(m=>m.content).join(' '));
    _dlog('TOKEN','est ~'+estTotal+' input tokens ('+msgs.length+' msgs)');
    const body={model:mdName,messages:msgs,temperature:0.7,max_tokens:4096,stream:false};
    const sUrl=streamUrl();let full='';
    show();const msgEl=document.createElement('div');msgEl.className='msg ai';bb=document.createElement('div');bb.className='b';bb.innerHTML='<div class="ty"><span></span><span></span><span></span></div>';msgEl.innerHTML='<div class="av">🤖</div>';msgEl.appendChild(bb);document.getElementById('chat').appendChild(msgEl);scrollChat();
    if(sUrl){
      body.stream=true;
      const r=await fetch(sUrl,{method:'POST',headers:apiHd(key),body:JSON.stringify(body)});
      if(!r.ok)throw new Error('HTTP '+r.status);
      const rd=r.body.getReader();const dc=new TextDecoder();let dbuf='',done=false,dp=0;
      let rendered=false;
      tw=setInterval(()=>{if(dp>=full.length){if(done&&!rendered){rendered=true;clearInterval(tw);bb.innerHTML=md(full);stat('完成');cleanup();return}return}dp=Math.min(dp+3,full.length);const t=full.slice(0,dp);bb.innerHTML='<p class="typing">'+esc(t)+'</p><div class="ty"><span></span><span></span><span></span></div>';scroll()},30);
      while(true){const{value,done:rd2}=await rd.read();if(rd2){done=true;break}dbuf+=dc.decode(value,{stream:true});const ls=dbuf.split('\n');dbuf=ls.pop()||'';for(const l of ls){if(!l.startsWith('data: '))continue;const d=l.slice(6).trim();if(d==='[DONE]'){done=true;break}try{const ch=JSON.parse(d);const dl=ch.choices?.[0]?.delta||{};if(dl.content)full+=dl.content}catch(e){}}if(done)break}
      full=_cleanToolMarkers(full);
      let w=0;while(dp<full.length&&w<10000){await new Promise(r2=>setTimeout(r2,100));w+=100}clearInterval(tw);
      if(full&&!rendered){bb.innerHTML=md(full);stat('完成');scrollChat()}
    }else{
      const r=await fetch(apiUrl(),{method:'POST',headers:apiHd(key),body:JSON.stringify(body)});const d=await r.json();
      if(!r.ok)throw new Error(d.error?.message||'HTTP '+r.status);
      full=_cleanToolMarkers(d.choices?.[0]?.message?.content||'(无内容)');bb.innerHTML=md(full);stat('完成');scrollChat();
    }
    if(full){
      // AI tool-use: detect [SEARCH:query] and execute
      const sm=full.match(/\[SEARCH:\s*([^\]]+)\]/i);
      if(sm&&location.protocol!=='file:'){
        const sq=sm[1].trim();
        full=await _runToolSearch(sq,hist,key,mdName,bb)||full;
      }
      hist.push({role:'assistant',content:full});CM.appendMessage('assistant',full);autoSave();_cacheSet(txt,full);
    }
  }catch(e){
    _dlog('SEND','error: '+e.message);
    if(bb)bb.innerHTML='❌ '+esc(e.message);
    stat('失败','var(--dng)');
  }finally{
    if(tw)clearInterval(tw);
    cleanup();
  }
}
function cleanup(){busy=false;document.getElementById('send').disabled=false;document.getElementById('input').focus();scrollChat()}
// ============ Built-in Web Search Tool ============
async function doWebSearch(query){
  if(busy)return;_dlog('WEBSEARCH',query);
  busy=true;document.getElementById('send').disabled=true;stat('搜索中…');
  addMsg('user','/search '+query);hist.push({role:'user',content:'/search '+query});CM.appendMessage('user','/search '+query);
  const key=document.getElementById('apikey').value.trim();
  let result='';
  try{
    const r=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,num:8})});
    if(!r.ok)throw new Error('HTTP '+r.status);
    const d=await r.json();
    const items=d.results||[];
    if(!items.length){result='**未找到相关结果。** 试试换个关键词？';}
    else{
      result='## 🌐 搜索结果: '+esc(query)+'\n\n';
      items.slice(0,8).forEach((it,i)=>{
        const t=esc(it.title||'无标题');const u=esc(it.url||'#');const s=esc((it.snippet||'').slice(0,200));
        result+='**'+(i+1)+'.** ['+t+']('+u+')\n> '+s+'\n\n';
      });
      result+='---\n*共 '+items.length+' 条结果。输入你的问题，AI 可基于这些结果回答。*';
    }
  }catch(e){result='❌ 搜索失败: '+esc(e.message);stat('搜索失败','var(--dng)')}
  addMsg('assistant',result);hist.push({role:'assistant',content:result});CM.appendMessage('assistant',result);autoSave();
  cleanup();stat('完成');
}
// ============ AI Tool-Use: Web Search ============
// When AI outputs [SEARCH:query], frontend runs search + feeds results back
async function _runToolSearch(query, prevMessages, key, mdName, bb){
  stat('AI 搜索中: '+query.slice(0,30)+'…');_dlog('TOOL','search: '+query);
  let sr='';
  try{
    const r=await fetch('/api/search',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({query,num:5})});
    if(r.ok){const d=await r.json();const items=d.results||[];
      if(items.length){sr=items.slice(0,5).map((it,i)=>`[${i+1}] ${it.title||''}\n${it.snippet||''}\n${it.url||''}`).join('\n\n');}}
  }catch(e){sr='搜索失败: '+e.message}
  if(!sr)sr='未找到结果。';
  const today=new Date();const ds=today.getFullYear()+'年'+(today.getMonth()+1)+'月'+today.getDate()+'日';
  const sp='今天是'+ds+'。\n\n以下是网页搜索结果:\n\n'+sr+'\n\n请基于以上搜索结果回答用户的问题。标注来源。如果结果不相关，用自己的知识回答。风格：专业犀利，不写客服体。';
  const body={model:mdName,messages:[{role:'system',content:sp},...prevMessages],temperature:0.7,max_tokens:4096,stream:false};
  const sUrl=streamUrl();let full='';
  if(sUrl){
    body.stream=true;
    try{
      const r2=await fetch(sUrl,{method:'POST',headers:apiHd(key),body:JSON.stringify(body)});
      if(!r2.ok)throw new Error('HTTP '+r2.status);
      const rd=r2.body.getReader();const dc=new TextDecoder();let dbuf='',done=false,dp=0;
      const tw=setInterval(()=>{if(dp>=full.length){if(done){clearInterval(tw);bb.innerHTML=md(full);stat('完成');cleanup();return}return}dp=Math.min(dp+3,full.length);const t=full.slice(0,dp);bb.innerHTML='<p class="typing">'+esc(t)+'</p><div class="ty"><span></span><span></span><span></span></div>';scroll()},30);
      while(true){const{value,done:rd2}=await rd.read();if(rd2){done=true;break}dbuf+=dc.decode(value,{stream:true});const ls=dbuf.split('\n');dbuf=ls.pop()||'';for(const l of ls){if(!l.startsWith('data: '))continue;const d=l.slice(6).trim();if(d==='[DONE]'){done=true;break}try{const ch=JSON.parse(d);const dl=ch.choices?.[0]?.delta||{};if(dl.content)full+=dl.content}catch(e){}}if(done)break}
      full=_cleanToolMarkers(full);
      let w=0;while(dp<full.length&&w<10000){await new Promise(r2=>setTimeout(r2,100));w+=100}clearInterval(tw);
      if(full)bb.innerHTML=md(full);
    }catch(e){bb.innerHTML='❌ '+esc(e.message);stat('失败','var(--dng)')}
  }else{
    try{const r2=await fetch(apiUrl(),{method:'POST',headers:apiHd(key),body:JSON.stringify(body)});const d2=await r2.json();
      if(!r2.ok)throw new Error(d2.error?.message||'HTTP '+r2.status);
      full=_cleanToolMarkers(d2.choices?.[0]?.message?.content||'');bb.innerHTML=md(full);stat('完成');scrollChat();
    }catch(e){bb.innerHTML='❌ '+esc(e.message);stat('失败','var(--dng)')}
  }
  return full;
}
function send(){const i=document.getElementById('input');const c=i.value.trim();if(!c)return;i.value='';
  if(c.startsWith('/search ')){doWebSearch(c.slice(8).trim());return}
  doSend(c);
}
function sendW(){const i=document.getElementById('winput');const c=i.value.trim();if(!c)return;i.value='';
  if(c.startsWith('/search ')){doWebSearch(c.slice(8).trim());return}
  doSend(c);
}
(function(){_dlog('INIT','marked='+(typeof marked!=='undefined')+' katex='+(typeof katex!=='undefined')+' hljs='+(typeof hljs!=='undefined'));loadChats();autoRestore();updateModelBadge();const i=document.getElementById('input');i.addEventListener('keydown',e=>{if(e.key=='Enter'&&!e.shiftKey){e.preventDefault();send()}});const w=document.getElementById('winput');w.addEventListener('keydown',e=>{if(e.key=='Enter'&&!e.shiftKey){e.preventDefault();sendW()}});document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key=='Enter'){e.preventDefault();send()}});stat('就绪 · 点 ⚙ 配置 API Key')})();