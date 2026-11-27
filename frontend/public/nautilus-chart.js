/* Nautilus native canvas chart. No third-party feed, remote script, or strategy.
   Epoch-based viewport persists independently of updates and contract rollovers. */
'use strict';
// A full day of 15-minute contracts covers the 18-hour chart viewport and
// keeps the start of an ordinary six-hour PAPER run inspectable.
const NAUTILUS_RESONANCE_ARCHIVE_LIMIT=96;
class NautilusChart {
  static BUILD_ID='0.0.8.4';
  static DISPLAY_REVISION='CASHOUT_NAUTILUS_COCKPIT_20261127';
  constructor(canvas, tooltip, onSelect) {
    this._listeners=[];this.destroyed=false;
    this.canvas=canvas; this.ctx=canvas.getContext('2d'); this.tooltip=tooltip;
    this.onSelect=onSelect; this.data=null; this.follow=true; this.end=null;
    this.fontScale=1; this.touches=new Map(); this.pinch=null; this.span=7200; this.fitTarget=false; this.manualY=null; this.manualDockY=null; this.dockRange=null; this.selected=null;
    this.showLookingGlass=true; this.reviewMode=false; this.viewportSpan=null;
    this.showLookingGlassInfo=true; this.onLookingGlassInfo=null; this.lookingGlassInfoKey=null;
    this.pointer=null; this.drag=null; this.markers=[]; this.ratio=.88; this.raf=0;
    // History and forecast have explicit, separate time scales. The dock starts
    // at the original 30% split, gains spare price-label space, and stays 15 minutes.
    this.forecastSeconds=900;this.forecastFraction=.30;this.pulseTimer=null;this.lastObservedRange=null;
    this.forecastPinned=false;this.pinnedForecast=null;this.pinnedForecastWindow=null;
    this.pinnedForecastRange=null;this.inspectionForecastRange=null;
    this.forecastRunKey=null; this.forecastArchive=new Map(); this.lastForecast=null; this.inspectionForecast=null;
    this.inspectionForecastWindow=null;this.featuredArchive=new Map();this.lastFeaturedForecast=null;
    // PUBLIC-DATA VISUALIZATION ONLY. Never used by strategy or order code.
    this.resetResonance();
    this.resetRoute();
    try { const n=Number(localStorage.getItem('nautilus.span')); if(n>=300&&n<=64800)this.span=n; } catch(e){}
    try { this.showLookingGlass=localStorage.getItem('nautilus.lookingGlass')!=='off'; } catch(e){}
    this.resizeObserver=new ResizeObserver(()=>this.requestDraw());
    this.resizeObserver.observe(canvas.parentElement);
    this.listen(canvas,'wheel',e=>this.wheel(e),{passive:false});
    this.listen(canvas,'pointerdown',e=>this.down(e));
    this.listen(canvas,'pointermove',e=>this.move(e));
    this.listen(canvas,'pointerup',e=>this.up(e));
    this.listen(canvas,'pointercancel',e=>this.cancelPointer(e));
    this.listen(canvas,'pointerleave',()=>{if(!this.drag){this.pointer=null;this.tooltip.classList.add('hidden');this.requestDraw();}});
    this.listen(canvas,'dblclick',e=>{const axis=this.priceAxisAt(e.offsetX);
      if(axis==='dock')this.fitDockScale();else if(axis==='history')this.manualY=null;
      else this.toLive();this.requestDraw();});
    this.listen(canvas,'keydown',e=>{
      if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();this.freezeViewport();this.end+=(e.key==='ArrowLeft'?-1:1)*this.viewSpan()/8;this.requestDraw();}
      if(e.key==='Home'){e.preventDefault();this.toLive();}
      if(e.key==='+'||e.key==='='){this.setSpan(this.span/1.2);}
      if(e.key==='-'){this.setSpan(this.span*1.2);}
    });
    if(typeof document!=='undefined'&&typeof document.addEventListener==='function')this.listen(document,'visibilitychange',()=>this.requestDraw());
    this.motionPreference=typeof window.matchMedia==='function'?window.matchMedia('(prefers-reduced-motion: reduce)'):null;
    if(this.motionPreference?.addEventListener)this.listen(this.motionPreference,'change',()=>this.requestDraw());
  }
  // App integration lifecycle; chart geometry and data interpretation are unchanged.
  listen(target,type,handler,options){target.addEventListener(type,handler,options);this._listeners.push([target,type,handler,options]);}
  destroy(){
    this.destroyed=true;
    this.resizeObserver?.disconnect();
    if(this.raf)cancelAnimationFrame(this.raf);
    if(this.pulseTimer!==null)clearTimeout(this.pulseTimer);
    for(const [target,type,handler,options] of this._listeners)target.removeEventListener(type,handler,options);
    this._listeners=[];this.raf=0;this.pulseTimer=null;this.data=null;this.onLookingGlassInfo=null;
  }
  saveSpan(){try{localStorage.setItem('nautilus.span',String(this.span));}catch(e){}}
  viewSpan(){return this.viewportSpan??this.span;}
  detached(value){return value==null?value:JSON.parse(JSON.stringify(value));}
  captureForecast(){
    const view=this.scenarioView({ignorePreference:true});
    return this.detached({...view,earlierTrails:this.dockFanPaths(view)
      .filter(item=>!item.selected).map(item=>({path:item.path,issue:item.issue}))});
  }
  freezeViewport(){
    if(this.follow){this.inspectionForecast=this.captureForecast();
      this.inspectionForecastWindow={...this.forecastWindow()};
      this.inspectionForecastRange=this.detached(this.manualDockY||this.forecastRange(this.inspectionForecast));}
    this.viewportSpan=this.viewSpan();this.follow=false;
  }
  setSpan(seconds,{persist=true}={}){this.span=Math.max(300,Math.min(64800,seconds));this.viewportSpan=this.span;if(persist)this.saveSpan();if(this.follow)this.syncLiveViewport();this.requestDraw();}
  historyEnd(){
    const candles=this.data?.candles||[],last=candles.at(-1);
    if(last?.complete===false&&Number.isFinite(this.data?.market?.time)&&
       this.data.market.time>=last.time&&this.data.market.time<last.time+60)
      return this.data.market.time;  // source-received last trade, not future minute close
    return last?last.time+60:Date.now()/1000;
  }
  futureRoomSeconds(){return 0;}
  liveEnd(){return this.historyEnd();}
  syncLiveViewport(){this.end=this.historyEnd();this.viewportSpan=this.span;}
  forecastWindow(){
    const held=this.forecastPinned?this.pinnedForecastWindow:!this.follow?this.inspectionForecastWindow:null;
    if(held)return {...held};
    // Follow the newest valid issue beside the latest source candle. Older
    // resonance geometry keeps its own timestamps; it never sets this clock.
    const key=this.contractKey(),saved=this.forecastArchive.get(key),valid=this.validScenario();
    const current=valid&&(!saved||valid.glass.source_ts>=saved.glass.source_ts)?valid:null;
    const chosen=current||saved||(this.resonance?.key===key?this.resonance.view:null)||this.lastForecast;
    const start=Number.isFinite(chosen?.glass?.source_ts)?chosen.glass.source_ts:
      Number.isFinite(this.data?.market?.time)?this.data.market.time:this.historyEnd();
    return {start,end:start+this.forecastSeconds,seconds:this.forecastSeconds};
  }
  toLive(){this.follow=true;this.inspectionForecast=null;this.inspectionForecastWindow=null;this.inspectionForecastRange=null;this.syncLiveViewport();this.requestDraw();}
  fitDockScale(){
    // Compatibility entry point: there is one shared BTC scale again.
    this.manualY=null;this.manualDockY=null;
  }
  fitPriceScale(){this.manualY=null;this.fitDockScale();this.fitTarget=false;this.requestDraw();}
  inspect(trade){this.freezeViewport();this.selected=trade;this.viewportSpan=this.span;this.manualY=null;const end=trade.exit_ts??trade.entry_ts+240;this.end=(trade.entry_ts+end)/2+this.span/2;this.requestDraw();}
  runKey(data=this.data){const id=data?.run?.run_id??data?.run?.name;return typeof id==='string'&&id.trim()?id:null;}
  entryBtcView(trade){return this.eventBtcView(trade,'entry');}
  exitBtcView(trade){return this.eventBtcView(trade,'exit');}
  eventBtcView(trade,event){
    if(!['entry','exit'].includes(event))return null;
    const source=trade?.[event+'_btc'],time=trade?.[event+'_ts'];
    if(source?.basis==='RECORDED_PAPER_EVENT_BTC_OBSERVATION'){
      if(source.available!==true||source.annotation!==false||source.event!==event||
         source.btc_fill_claim!==false||source.execution_authority!==false||
         source.source!=='RECORDED_PAPER_JOURNAL'||
         source.run_id!==this.runKey()||source.ticker!==trade.ticker||source.side!==trade.side||
         String(source.position_id)!==String(trade.position_id??trade.trade_id)||
         !Number.isFinite(time)||source.paper_event_ts!==time||
         ![source.price,source.observed_at,source.received_ts].every(Number.isFinite)||
         source.price<=0||source.observed_at<=0||source.received_ts!==source.observed_at||
         source.observed_at>time+1e-6||time-source.observed_at>3+1e-6)return null;
      return source;
    }
    // Preserve older rich entry observations without treating one as the
    // exit observation. Old records lacking either event remain annotations.
    if(event!=='entry')return null;
    if(source?.available!==true||source.basis!=='RECORDED_ENTRY_BTC_OBSERVATION'||
       source.btc_fill_claim!==false||source.execution_authority!==false||
       source.run_id!==this.runKey()||source.ticker!==trade.ticker||source.side!==trade.side||
       String(source.position_id)!==String(trade.position_id??trade.trade_id)||
       !Number.isFinite(trade.entry_ts)||source.entry_ts!==trade.entry_ts||
       ![source.price,source.event_ts,source.received_ts].every(Number.isFinite)||source.price<=0||
       source.event_ts<=0||source.event_ts>source.received_ts+1e-6||source.received_ts>trade.entry_ts+1e-6||
       trade.entry_ts-source.event_ts>3+1e-6||trade.entry_ts<source.event_ts||
       ![source.source_row_id,source.last_trade_id].every(value=>typeof value==='string'&&value.length>0)||
       ![source.connection_epoch,source.sample_serial].every(value=>Number.isInteger(value)&&value>=0))return null;
    return source;
  }
  contractKey(data=this.data){return `${this.runKey(data)}|${data?.market?.ticker??''}|${data?.market?.close_ts??''}`;}
  currentTargetContext(data=this.data){
    const market=data?.market;if(!market||!Number.isFinite(market.close_ts))return null;
    const saved=(data.targets||[]).find(target=>target.ticker===market.ticker&&target.close_ts===market.close_ts);
    const target=Number.isFinite(market.target)?market.target:saved?.target;
    return Number.isFinite(target)&&target>0?{ticker:market.ticker,close_ts:market.close_ts,start_ts:market.close_ts-900,target}:null;
  }
  targetSegments(from,end){
    // A historical target belongs to one finite contract. Missing endpoints
    // never become an indefinitely extended horizontal price level.
    const found=new Map();
    for(const target of this.data?.targets||[]){
      if(typeof target.ticker!=='string'||!target.ticker||
         ![target.start_ts,target.close_ts,target.target].every(Number.isFinite)||
         target.target<=0||target.close_ts<=target.start_ts||
         target.start_ts>=end||target.close_ts<=from)continue;
      const key=[target.ticker,target.start_ts,target.close_ts].join('|');
      found.set(key,{...target,start:Math.max(from,target.start_ts),end:Math.min(end,target.close_ts)});
    }
    return [...found.values()].sort((a,b)=>a.start_ts-b.start_ts);
  }
  drawTargetSegments(from,end,map,{dock=false}={}){
    for(const target of this.targetSegments(from,end)){
      const a=map(target.start),b=map(target.end),y=dock?this.dockY(target.target):this.y(target.target);
      const active=target.ticker===this.data?.market?.ticker&&target.close_ts===this.data?.market?.close_ts;
      // FOCUS VISUAL ONLY: strong glow on a source-verified target segment.
      // Keep the same contract-bounded endpoints; never draw an imaginary TP
      // through another contract or project a future target.
      if(this.focusVisual){
        const c=this.ctx;c.save();c.shadowColor=active?'#ffc34e':'#ce9f66';
        c.shadowBlur=active?16:7;
        this.line(a,y,b,y,active?'#ffc253':'#bb9859b0',active?3.2:2.0,[8,5]);c.restore();
      }else this.line(a,y,b,y,active?'#efbd5baa':'#c9a36a70',active?1.2:1,[5,4]);
      if(y>this.top+12&&y<this.mainBottom-12&&b-a>(this.focusVisual?58:90)){
        const label=this.focusVisual?'TP $'+this.price(target.target):
          (active?'TO BEAT ':'TP '+this.clock(target.close_ts)+' ')+'$'+this.price(target.target);
        this.text(label,b-5,y-(this.focusVisual?9:6),active?'#ffd275':'#bca17c',this.focusVisual?13:dock?8:9,'right');
      }
    }
  }
  setData(data){
    const runKey=this.runKey(data);
    if(runKey===null||(this.forecastRunKey!==null&&this.forecastRunKey!==runKey)){
      this.forecastArchive.clear();this.featuredArchive.clear();this.lastFeaturedForecast=null;
      this.lookingGlassInfoKey=null;
      this.lastObservedRange=null;
      this.dockRange=null;this.manualDockY=null;this.pinnedForecastRange=null;this.inspectionForecastRange=null;
      this.lastForecast=null;this.pinnedForecast=null;this.pinnedForecastWindow=null;
      this.inspectionForecast=null;this.inspectionForecastWindow=null;this.forecastPinned=false;this.resetRoute();
      this.resetResonance({clearArchive:true});
    }
    this.forecastRunKey=runKey;this.data=data;
    const valid=this.validScenario(data);
    if(valid){
      const key=this.contractKey(data),previous=this.forecastArchive.get(key);
      if(!previous||valid.glass.source_ts>=previous.glass.source_ts){
        // Detached values prevent a later mutable polling payload from
        // moving a previously issued line or changing its provenance.
        const saved=JSON.parse(JSON.stringify({...valid,key,runKey}));
        this.forecastArchive.set(key,saved);this.lastForecast=saved;
        while(this.forecastArchive.size>12)this.forecastArchive.delete(this.forecastArchive.keys().next().value);
        for(const sample of valid.issuedSamples||[])this.rememberFeatured(this.featureFromIssued(sample));
        if(valid.active)this.rememberFeatured(this.featureFromView(valid,data));
      }
    }
    this.updateResonance(data,valid);
    this.updateRoute(data);
    if(this.end===null||this.follow)this.syncLiveViewport();this.requestDraw();
  }
  resetResonance({clearArchive=false}={}){
    if(clearArchive||!this.resonanceArchive)this.resonanceArchive=new Map();
    this.resonance={key:null,issue:null,close:null,tolerance:20,paths:[],
      counts:{},segments:{},stats:{},observations:[],view:null,reference:null,
      lastSampleBucket:-1,lastObservedTime:-Infinity};
  }
  resonanceIdentity(path){
    // A frozen record can be keyed directly by its original source identity.
    if(typeof path?.key==='string'&&/^(H:|ID:)/.test(path.key))return path.key;
    // Original completed-historical-window identity survives reanchoring and
    // a changing index in the rolling comparison fan.
    if(Number.isFinite(path?.historical_source_start_ts)&&
       Number.isFinite(path?.historical_source_end_ts))
      return `H:${path.historical_source_start_ts}:${path.historical_source_end_ts}`;
    return typeof path?.id==='string'?`ID:${path.id}`:null;
  }
  resonanceInterpolation(points,time){
    if(!Array.isArray(points)||points.length<2||time<points[0].time||time>points.at(-1).time)return null;
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i];
      if(time<=b.time&&Number.isFinite(a.btc)&&Number.isFinite(b.btc)&&b.time>a.time)
        return {btc:a.btc+(b.btc-a.btc)*(time-a.time)/(b.time-a.time),segment:i-1};
    }
    return null;
  }
  comparisonEligible(view){
    const glass=view?.glass,observed=glass?.observations;
    const sign={UP:1,DOWN:-1,FLAT:0}[observed?.ema9_direction];
    return glass?.comparison_ready!==false&&sign!==undefined&&
      Number.isFinite(observed?.ema9_slope_per_min)&&Math.sign(observed.ema9_slope_per_min)===sign;
  }
  resonanceRestore(key,now){
    try{
      const saved=JSON.parse(localStorage.getItem('nautilus.resonance.v2')||'null');
      const run=key.split('|')[0];
      if(saved?.version!==2||saved.run_id!==run)return false;
      const validRecord=raw=>raw&&typeof raw.key==='string'&&raw.run_id===run&&
        Number.isFinite(raw.issue)&&Number.isFinite(raw.close)&&
        Array.isArray(raw.paths)&&raw.paths.length>0&&raw.paths.length<=12&&
        raw.paths.every(p=>typeof p.key==='string'&&Array.isArray(p.points)&&
          p.points.length>=2&&p.points.length<=32&&p.points.every((pt,i)=>
            Number.isFinite(pt.time)&&Number.isFinite(pt.btc)&&pt.btc>0&&
            pt.time>=raw.issue&&(i===0||pt.time>p.points[i-1].time)));
      for(const record of (Array.isArray(saved.archive)?saved.archive:[]).slice(-NAUTILUS_RESONANCE_ARCHIVE_LIMIT)){
        // Migrate an older signed cohort without moving it. An initial cohort
        // frozen before any signed slope is not an accepted current issue.
        if(record.key===key&&!this.comparisonEligible(saved.current?.view))continue;
        if(validRecord(record)&&record.issue<=now&&!this.resonanceArchive.has(record.key))
          this.resonanceArchive.set(record.key,record);
      }
      const raw=saved.current;
      if(raw?.key!==key||!Number.isFinite(raw.issue)||!Number.isFinite(raw.close)||
         !Number.isFinite(now)||raw.issue>now||now>raw.close+90||
         !validRecord(raw)||!this.comparisonEligible(raw.view)||!raw.stats||!raw.counts||!raw.segments||
         !Array.isArray(raw.observations)||raw.observations.length>1000||
         raw.observations.some(pt=>!Number.isFinite(pt.time)||!Number.isFinite(pt.btc)||
           pt.btc<=0||pt.time<raw.issue||pt.time>now)||
         !Number.isFinite(raw.tolerance)||raw.tolerance<1||raw.tolerance>100)return false;
      this.resonance={...raw,lastObservedTime:Number.isFinite(raw.lastObservedTime)?raw.lastObservedTime:-Infinity};
      return true;
    }catch(e){return false;}
  }
  resonanceSave(){
    try{localStorage.setItem('nautilus.resonance.v2',JSON.stringify({version:2,
      run_id:this.resonance.run_id,current:this.resonance,
      archive:[...this.resonanceArchive.values()].slice(-NAUTILUS_RESONANCE_ARCHIVE_LIMIT)}));}catch(e){}
  }
  rememberResonanceGeometry(){
    const r=this.resonance;
    if(!r?.paths.length||!Number.isFinite(r.issue)||this.resonanceArchive.has(r.key))return;
    // Only immutable issued geometry is archived. Earned colors and scores
    // belong to one contract and do not pass into the next contract.
    this.resonanceArchive.set(r.key,this.detached({key:r.key,run_id:r.run_id,
      ticker:r.ticker,issue:r.issue,close:r.close,paths:r.paths,reference:r.reference}));
    while(this.resonanceArchive.size>NAUTILUS_RESONANCE_ARCHIVE_LIMIT)
      this.resonanceArchive.delete(this.resonanceArchive.keys().next().value);
  }
  retainResonanceTrails(){
    // Only display selection is saved at rollover. Every issued vertex stays
    // unchanged, and earned colors/scores never pass into the next contract.
    const r=this.resonance,record=this.resonanceArchive.get(r?.key);
    if(!record)return;
    const trail_keys=this.resonanceRanking().filter(item=>item.visits>0)
      .slice(0,2).map(item=>item.key);
    this.resonanceArchive.set(r.key,{...record,trail_keys});
  }
  updateResonance(data,valid){
    // One as-issued set per contract. Observations may score it only after
    // issue time; current newly reanchored paths are NEVER self-scored.
    const key=this.contractKey(data),now=data?.market?.time,price=data?.market?.btc;
    if(!data?.market?.ticker||!Number.isFinite(data?.market?.close_ts))return;
    if(this.resonance.key!==key){
      this.retainResonanceTrails();
      this.resetResonance();
      if(!this.resonanceRestore(key,now))this.resonance.key=key;
    }
    const r=this.resonance;
    // A supplied receive clock bounds what could have been observed. A bad
    // future timestamp cannot earn a match, even if its freshness flag is set.
    if(Number.isFinite(data?.server_now)&&
       (!Number.isFinite(now)||now>data.server_now||data.server_now-now>3))return;
    if(r.issue===null&&valid?.paths?.length&&this.comparisonEligible(valid)&&data?.market?.fresh===true&&
       data?.run?.fresh===true&&!data.run.stopped){
      const issue=valid.glass.source_ts,close=valid.glass.close_ts;
      const paths=valid.paths.map(path=>({...this.detached(path),key:this.resonanceIdentity(path)}))
        .filter(path=>path.key&&path.points.length>=2);
      if(!paths.length)return;
      // Historical *completed* bar ranges available at the issue instant.
      // This scale is fixed for the contract and never revised using hindsight.
      const bars=(data.candles||[]).filter(b=>b.complete===true&&b.time+60<=issue&&
        (!Number.isFinite(b.known_at)||b.known_at<=issue)&&
        [b.high,b.low].every(Number.isFinite)&&b.high>=b.low).slice(-12);
      const ranges=bars.map(b=>b.high-b.low).sort((a,b)=>a-b);
      const typical=ranges.length?ranges[Math.floor(ranges.length/2)]:25;
      r.issue=issue;r.close=close;r.paths=paths;r.run_id=this.runKey(data);r.ticker=data.market.ticker;
      {const k=this.data?.asset?.normalization||1;r.tolerance=Math.max(10/k,Math.min(45/k,typical*.7));}
      r.counts={};r.segments={};r.stats={};
      r.observations=[{time:issue,btc:paths[0].points[0].btc}];
      r.lastSampleBucket=-1;r.lastObservedTime=-Infinity;
      const reference=this.referenceFromView({...valid,paths});
      r.reference=reference.reference;
      r.view=this.detached({...valid,paths,reference:r.reference,referenceReason:reference.reason,
        frozen_comparison:true,key,runKey:r.run_id});
      this.rememberResonanceGeometry();
      this.resonanceSave();
    }
    if(r.issue===null||!Number.isFinite(now)||!Number.isFinite(price)||price<=0||
       data.market.fresh!==true||data?.run?.fresh!==true||data.run.stopped||
       now<r.issue+20||now>=r.close||now<=r.lastObservedTime)return;
    const bucket=Math.floor((now-r.issue)/12);
    if(bucket<=r.lastSampleBucket)return; // browser polls never count as visits
    r.lastSampleBucket=bucket;r.lastObservedTime=now;
    // Compare the observed elapsed path with the same elapsed times on each
    // pre-issued route. Accumulated distance and direction agreement prevent
    // a line on the wrong side from becoming bright just by crossing once.
    const previous=r.observations.at(-1),actualMove=previous?price-previous.btc:0;
    r.observations.push({time:now,btc:price});
    if(r.observations.length>1000)r.observations.splice(1,r.observations.length-1000);
    const matches=[];
    for(const path of r.paths){
      const sampled=this.resonanceInterpolation(path.points,now);
      if(!sampled)continue;
      const distance=Math.abs(sampled.btc-price);
      const before=previous?this.resonanceInterpolation(path.points,previous.time):null;
      const projectedMove=before?sampled.btc-before.btc:0;
      const directional=Math.abs(actualMove)>r.tolerance*.1&&Math.abs(projectedMove)>r.tolerance*.1;
      const agrees=!directional||Math.sign(actualMove)===Math.sign(projectedMove);
      const stat=r.stats[path.key]||{samples:0,error:0,directions:0,mismatches:0,lastDistance:0};
      stat.samples++;stat.error+=Math.min(6,distance/r.tolerance);stat.lastDistance=distance;
      if(directional){stat.directions++;if(!agrees)stat.mismatches++;}
      r.stats[path.key]=stat;
      if(distance<=r.tolerance&&agrees)matches.push({path,segment:sampled.segment,distance,
        score:stat.error/stat.samples+.65*(stat.directions?stat.mismatches/stat.directions:0)});
    }
    matches.sort((a,b)=>a.score-b.score||a.distance-b.distance||a.path.key.localeCompare(b.path.key));
    for(const {path,segment} of matches.slice(0,2)){
      r.counts[path.key]=Math.min(1000,(r.counts[path.key]||0)+1);
      const segments=r.segments[path.key]||Array(path.points.length-1).fill(0);
      segments[segment]=Math.min(1000,segments[segment]+1);
      r.segments[path.key]=segments;
    }
    this.resonanceSave();
  }
  resonanceVisits(path){
    return this.resonance?.counts?.[this.resonanceIdentity(path)]||0;
  }
  resonanceRanking(){
    const r=this.resonance;
    return (r?.paths||[]).map(path=>{
      const key=this.resonanceIdentity(path),s=r.stats?.[key];
      if(!s?.samples)return null;
      return {key,path,visits:r.counts[key]||0,samples:s.samples,distance:s.lastDistance,
        score:s.error/s.samples+.65*(s.directions?s.mismatches/s.directions:0)};
    }).filter(Boolean).sort((a,b)=>a.score-b.score||a.distance-b.distance||a.key.localeCompare(b.key));
  }
  resonanceStyle(path,archived=false){
    if(archived)return {alpha:.40,width:1.1,emphasized:false};
    const ranking=this.resonanceRanking(),key=this.resonanceIdentity(path),r=this.resonance;
    if(!ranking.length)return {alpha:.44,width:1.15,emphasized:false};
    const candidates=ranking.filter(item=>item.visits>0&&item.score<=1.2&&item.distance<=r.tolerance*1.5).slice(0,2);
    const rank=candidates.findIndex(item=>item.key===key),visits=this.resonanceVisits(path);
    if(rank<0)return {alpha:.44,width:1.15,emphasized:false};
    return {alpha:Math.min(rank===0 ? .96 : .72,(rank===0 ? .55 : .37)+Math.sqrt(visits)*.07),
      width:Math.min(rank===0?3.8:2.7,(rank===0?1.7:1.2)+Math.sqrt(visits)*.32),emphasized:true,rank};
  }
  drawResonance(path,map,color,mapY=value=>this.y(value)){
    const visits=this.resonanceVisits(path),style=this.resonanceStyle(path);
    if(!visits||!style.emphasized||!Array.isArray(path.points))return;
    const c=this.ctx;
    c.save();c.strokeStyle=color;c.setLineDash([]);
    c.globalAlpha=style.alpha;c.lineWidth=style.width;
    c.shadowColor=color;c.shadowBlur=style.rank===0?Math.min(6,1+Math.sqrt(visits)):0;
    c.beginPath();path.points.forEach((pt,i)=>{
      if(i===0)c.moveTo(map(pt.time),mapY(pt.btc));
      else c.lineTo(map(pt.time),mapY(pt.btc));
    });c.stroke();
    // Local segment memory identifies which sections were actually approached.
    const counts=this.resonance.segments[this.resonanceIdentity(path)]||[];
    counts.forEach((count,i)=>{
      if(!count||i+1>=path.points.length)return;
      const a=path.points[i],b=path.points[i+1],end=Math.min(b.time,this.resonance.lastObservedTime);
      if(end<=a.time)return;
      const price=a.btc+(b.btc-a.btc)*(end-a.time)/(b.time-a.time);
      c.beginPath();c.lineWidth=Math.min(4.6,style.width+.5+Math.sqrt(count)*.2);
      c.globalAlpha=style.alpha;
      c.moveTo(map(a.time),mapY(a.btc));c.lineTo(map(end),mapY(price));c.stroke();
    });
    c.restore();
  }
  setLookingGlass(enabled){this.showLookingGlass=Boolean(enabled);try{localStorage.setItem('nautilus.lookingGlass',enabled?'on':'off');}catch(e){}this.requestDraw();}
  setForecastPinned(enabled){
    if(enabled){
      if(this.forecastPinned)return;
      const displayed=this.scenarioView({ignorePreference:true});if(!displayed.paths.length&&!displayed.featured)return;
      this.pinnedForecast=this.captureForecast();this.pinnedForecastWindow={...this.forecastWindow()};
      this.pinnedForecastRange=this.detached(this.manualDockY||this.forecastRange(displayed));this.forecastPinned=true;
    }else{this.pinnedForecast=null;this.pinnedForecastWindow=null;this.pinnedForecastRange=null;this.forecastPinned=false;}
    this.requestDraw();
  }
  scenarioHorizon(glass){
    if(!glass||typeof glass!=='object')return null;
    const declared=['horizon_end_ts','horizon_seconds','horizon_mode','projection_scope'].some(key=>Object.prototype.hasOwnProperty.call(glass,key));
    if(!declared&&glass.version!=='LOOKING_GLASS_V3_ROLLING_PHYSICAL')return {end:glass.close_ts,rolling:false};
    if(glass.version!=='LOOKING_GLASS_V3_ROLLING_PHYSICAL'||glass.horizon_mode!=='ROLLING_PHYSICAL'||
       glass.projection_scope!=='BTC_EMA9_PHYSICAL_ONLY'||glass.horizon_seconds!==900||
       !Number.isFinite(glass.source_ts)||!Number.isFinite(glass.horizon_end_ts)||
       Math.abs(glass.horizon_end_ts-glass.source_ts-900)>1e-6||
       !Number.isFinite(glass.close_ts)||glass.close_ts<=glass.source_ts||glass.close_ts>glass.horizon_end_ts)return null;
    return {end:glass.horizon_end_ts,rolling:true};
  }
  validScenario(data=this.data){
    const glass=data?.looking_glass,market=data?.market;
    if(!glass||!market||!this.runKey(data)||data?.run?.review||!['READY','PARTIAL'].includes(glass.status))return null;
    if(!Number.isFinite(glass.source_ts)||!Number.isFinite(glass.valid_until)||glass.valid_until<glass.source_ts)return null;
    if(glass.execution_authority!==false||glass.probabilities_calibrated!==false||
       glass.ticker!==market.ticker||glass.close_ts!==market.close_ts||
       !Number.isFinite(glass.close_ts)||glass.close_ts<=glass.source_ts||
       !Number.isFinite(market.time)||Math.abs(market.time-glass.source_ts)>3)
      return null;
    const horizon=this.scenarioHorizon(glass);if(!horizon)return null;
    const paths=(Array.isArray(glass.paths)?glass.paths:[]).filter(path=>{
      if(path.conditional!==true||!['CONTINUATION','ROTATION_STALL','REVERSAL','PATTERN'].includes(path.family)||!Array.isArray(path.points)||path.points.length<2)return false;
      const first=path.points[0],last=path.points.at(-1);
      const finitePattern=path.family==='PATTERN';
      if(finitePattern&&(!Number.isFinite(path.horizon_ts)||Math.abs(last.time-path.horizon_ts)>1e-6||
         path.time_stretched!==false||path.repeated!==false||!Number.isFinite(path.reference_end_ts)||
         path.reference_end_ts>glass.close_ts-900||path.reference_known_by_ts!==glass.source_ts))return false;
      if(Math.abs(first.time-glass.source_ts)>1e-6||(!finitePattern&&Math.abs(last.time-horizon.end)>1e-6)||
         !Number.isFinite(market.btc)||Math.abs(first.btc-market.btc)>1e-6||
         !Number.isFinite(market.e9)||Math.abs(first.e9-market.e9)>1e-6)return false;
      return path.points.every((point,index)=>Number.isFinite(point.time)&&Number.isFinite(point.btc)&&point.btc>0&&
        Number.isFinite(point.e9)&&point.e9>0&&point.time>=glass.source_ts&&point.time<=horizon.end&&
        (index===0||point.time>path.points[index-1].time));
    }).slice(0,12);
    if(!paths.length)return null;
    const physical=data?.health?.physical,admission=physical?.history_admission,
      divergenceReason='CONFIRMED_REST_DIFFERS_FROM_CONTINUOUS_LIVE';
    // WARNING is not general verification. Only the explicitly qualified,
    // current canonical-live divergence condition may retain verified history.
    // Store the issued classification in the detached bundle for pin/inspection.
    const verifiedDivergence=physical?.status==='WARNING'&&physical.reason===divergenceReason&&
      physical.canonical_history_current===true&&physical.source_divergence_verified===true&&
      admission?.status==='SOURCE_DIVERGENCE'&&admission.source_warning===divergenceReason&&
      admission.current_error===null&&admission.conflict_count===0&&
      admission.pending_discrepancy_count===0&&admission.pending_confirmation_count===0&&
      Number.isInteger(admission.source_divergence_count)&&admission.source_divergence_count>0&&
      data?.tool_rack?.physical_current===true&&data?.run?.fresh===true&&!data.run.stopped&&market.fresh===true&&
      Number.isFinite(physical.updated)&&Number.isFinite(data.server_now)&&
      data.server_now>=physical.updated&&data.server_now-physical.updated<=5&&
      physical.updated>=glass.source_ts-2&&physical.updated<=glass.valid_until&&data.server_now<=glass.valid_until;
    const view={glass,paths,active:null,issued:null,horizon_ts:horizon.end,rolling:horizon.rolling,
      physicalHealth:{status:typeof physical?.status==='string'?physical.status:'UNKNOWN',reason:physical?.reason||null,
        conflict_count:admission?.conflict_count??null,
        canonical_history_current:physical?.canonical_history_current===true,
        source_divergence_verified:verifiedDivergence},
      targetContext:this.currentTargetContext(data),calendar_close_ts:market.close_ts},active=glass.active_pattern;
    const activePath=paths.find(path=>path.id===active?.path_id);
    if(active?.status==='READY'&&active.conditional===true&&active.execution_authority===false&&
       active.source_ts===glass.source_ts&&typeof active.key==='string'&&
       activePath&&Number.isFinite(active.horizon_ts)&&Math.abs(active.horizon_ts-activePath.points.at(-1).time)<1e-6)view.active=active;
    // Frozen samples remain inspectable when the newest issue has no active
    // pattern. They retain their own anchors and never become current proof.
    view.issuedSamples=this.validIssuedSamples(glass,data);
    if(view.active)view.issued=view.issuedSamples.find(sample=>sample.source_ts<glass.source_ts&&
      sample.pattern_key===active.key&&sample.continuity_generation===active.continuity_generation)||null;
    return view;
  }
  validIssuedSamples(glass,data=this.data){
    const now=typeof this.sourceClock==='function'?this.sourceClock():data?.server_now;
    const generation=glass.active_pattern?.continuity_generation;
    if(!Number.isInteger(generation)||generation<0)return [];
    return (Array.isArray(glass.research?.as_issued)?glass.research.as_issued:[]).slice(-16).filter(sample=>{
      if(!sample||sample.frozen!==true||sample.conditional!==true||sample.execution_authority!==false||
         sample.run_id!==this.runKey(data)||sample.ticker!==glass.ticker||sample.close_ts!==glass.close_ts||
         typeof sample.pattern_key!=='string'||!sample.pattern_key.trim()||
         !Number.isInteger(sample.continuity_generation)||sample.continuity_generation<0||
         sample.continuity_generation!==generation||
         !Number.isFinite(now)||!Number.isFinite(sample.source_ts)||sample.source_ts>glass.source_ts||
         !Number.isFinite(sample.issued_at_ts)||sample.issued_at_ts>now||sample.issued_at_ts<sample.source_ts||
         !Array.isArray(sample.path?.points)||sample.path.points.length<2)return false;
      const horizon=this.scenarioHorizon(sample),path=sample.path,points=path.points,anchor=sample.anchor;
      if(!horizon||!Number.isFinite(horizon.end)||horizon.end<=sample.source_ts||
         !['CONTINUATION','ROTATION_STALL','REVERSAL','PATTERN'].includes(path.family)||path.conditional!==true)return false;
      const first=points[0],last=points.at(-1);
      if(path.family==='PATTERN'){
        if(!Number.isFinite(path.horizon_ts)||Math.abs(path.horizon_ts-last.time)>1e-6||
           path.time_stretched!==false||path.repeated!==false||!Number.isFinite(path.reference_end_ts)||
           path.reference_end_ts>sample.close_ts-900||path.reference_known_by_ts!==sample.source_ts)return false;
      }else if(horizon.rolling&&Math.abs(last.time-horizon.end)>1e-6)return false;
      return anchor&&first.time===sample.source_ts&&first.time===anchor.time&&
        first.btc===anchor.btc&&first.e9===anchor.e9&&points.every((point,index)=>
          Number.isFinite(point.time)&&point.time>=sample.source_ts&&point.time<=horizon.end&&
          Number.isFinite(point.btc)&&point.btc>0&&Number.isFinite(point.e9)&&point.e9>0&&
          (index===0||point.time>points[index-1].time));
    });
  }
  featureFromView(view,data=this.data){
    const path=view.paths.find(path=>path.id===view.active?.path_id);if(!path)return null;
    return this.detached({path,pattern:view.active,run_id:this.runKey(data),ticker:view.glass.ticker,
      close_ts:view.glass.close_ts,source_ts:view.glass.source_ts,issued_at_ts:view.glass.source_ts,
      horizon_ts:path.points.at(-1).time,issue_horizon_ts:view.horizon_ts,
      valid_until:view.glass.valid_until,continuity_generation:view.active.continuity_generation,
      original_reason:view.active.reason});
  }
  featureFromIssued(sample){
    const horizon=this.scenarioHorizon(sample);if(!horizon)return null;
    return this.detached({path:sample.path,pattern:{key:sample.pattern_key,path_id:sample.path.id,
      label:sample.label||'Earlier featured path',source_ts:sample.source_ts,
      horizon_ts:sample.path.points.at(-1).time,continuity_generation:sample.continuity_generation,
      conditional:true,execution_authority:false},run_id:sample.run_id,ticker:sample.ticker,
      close_ts:sample.close_ts,source_ts:sample.source_ts,issued_at_ts:sample.issued_at_ts,
      horizon_ts:sample.path.points.at(-1).time,issue_horizon_ts:horizon.end,
      valid_until:sample.source_ts,continuity_generation:sample.continuity_generation,
      original_reason:'Frozen original issued feature; current qualification is not implied.'});
  }
  rememberFeatured(feature){
    if(!feature||feature.run_id!==this.runKey())return;
    const key=[feature.run_id,feature.ticker,feature.close_ts,feature.continuity_generation,feature.pattern.key].join('|');
    const previous=this.featuredArchive.get(key);if(previous&&previous.source_ts>feature.source_ts)return;
    const saved=this.detached(feature);this.featuredArchive.delete(key);this.featuredArchive.set(key,saved);
    while(this.featuredArchive.size>16)this.featuredArchive.delete(this.featuredArchive.keys().next().value);
    if(!this.lastFeaturedForecast||saved.source_ts>=this.lastFeaturedForecast.source_ts)this.lastFeaturedForecast=saved;
  }
  hasForwardSegment(item,window=this.forecastWindow()){
    const points=item?.path?.points||[];
    return points.some((point,index)=>index>0&&
      Math.max(points[index-1].time,window.start)<Math.min(point.time,window.end));
  }
  referenceFromView(view){
    // This selects an already issued comparison; it does not detect a pattern,
    // create geometry, rank win probabilities, or populate the feature cache.
    const glass=view?.glass,observed=glass?.observations,direction=observed?.ema9_direction,
      slope=observed?.ema9_slope_per_min,sign={UP:1,DOWN:-1,FLAT:0}[direction];
    const unavailable=reason=>({reference:null,reason});
    if(!view?.rolling||!Number.isFinite(slope)||sign===undefined||Math.sign(slope)!==sign)
      return unavailable('Reference unavailable · observed EMA9 direction or slope is unknown');
    const candidates=[];
    for(const path of view.paths){
      if(!['CONTINUATION','ROTATION_STALL','REVERSAL'].includes(path.family)||
         typeof path.id!=='string'||!path.id.trim()||
         !Array.isArray(path.reference_ids)||!path.reference_ids.length||
         !path.reference_ids.every(id=>typeof id==='string'&&id.trim())||
         !Number.isFinite(path.reference_start_ts)||!Number.isFinite(path.reference_end_ts)||
         path.reference_start_ts>=path.reference_end_ts||path.reference_end_ts>glass.close_ts-900||
         path.reference_known_by_ts!==glass.source_ts||path.time_stretched!==false||path.repeated!==false||
         path.reference_alignment!=='PROFILE_START_AT_ISSUE_TIME'||path.reference_duration_seconds!==900)continue;
      if(sign===0&&path.family!=='ROTATION_STALL')continue;
      let rate=0;
      for(let index=1;index<path.points.length;index++){
        const a=path.points[index-1],b=path.points[index],change=b.e9-a.e9;
        if(change!==0){rate=change*60/(b.time-a.time);break;}
      }
      if(!Number.isFinite(rate)||(sign!==0&&Math.sign(rate)!==sign))continue;
      candidates.push({path,rate,distance:Math.abs(rate-slope)});
    }
    candidates.sort((a,b)=>a.distance-b.distance||b.path.reference_end_ts-a.path.reference_end_ts||
      (a.path.id<b.path.id?-1:a.path.id>b.path.id?1:0));
    if(!candidates.length)return unavailable('Reference unavailable · no comparable issued historical path');
    const {path,rate}=candidates[0],family={CONTINUATION:'Continuation',ROTATION_STALL:'Rotation / stall',REVERSAL:'Return / reversal'}[path.family];
    return {reference:this.detached({kind:'CONDITIONAL_DISPLAY_REFERENCE',path,label:family+' reference',
      run_id:this.runKey(),ticker:glass.ticker,close_ts:glass.close_ts,source_ts:glass.source_ts,
      horizon_ts:path.points.at(-1).time,issue_horizon_ts:view.horizon_ts,valid_until:glass.valid_until,
      conditional:true,execution_authority:false,engine_pattern:false,selection_is_probability:false,
      observed_direction:direction,observed_ema9_slope_per_min:slope,reference_initial_ema9_slope_per_min:rate,
      selection_basis:'SIGNED_INITIAL_EMA9_SLOPE_THEN_RECENT_REFERENCE_THEN_ID',
      physical_status_at_issue:view.physicalHealth?.status||'UNKNOWN',
      physical_reason_at_issue:view.physicalHealth?.reason||null,
      history_verified_at_issue:(view.physicalHealth?.status==='CURRENT'&&!(view.physicalHealth?.conflict_count>0))||
        (view.physicalHealth?.status==='WARNING'&&view.physicalHealth?.canonical_history_current===true&&
         view.physicalHealth?.source_divergence_verified===true&&view.physicalHealth?.conflict_count===0),
      source_divergence_verified_at_issue:view.physicalHealth?.source_divergence_verified===true,
      original_reason:'One already issued historical comparison, selected by observed EMA9 direction and initial slope. Its original points, scale and times are unchanged; this is not an engine pattern or a win score.'}),reason:null};
  }
  scenarioView({ignorePreference=false,ignoreViewport=false}={}){
    const empty=(status,reason)=>({status,reason,paths:[],glass:null,active:null,displayActive:null,featured:null,reference:null,referenceReason:reason,issued:null,retained:false,horizon_ts:null,rolling:false,
      targetContext:this.forecastPinned?this.pinnedForecast?.targetContext:!this.follow?this.inspectionForecast?.targetContext:this.currentTargetContext(),
      calendar_close_ts:this.forecastPinned?this.pinnedForecast?.calendar_close_ts:!this.follow?this.inspectionForecast?.calendar_close_ts:this.data?.market?.close_ts});
    if(!ignorePreference&&!this.showLookingGlass)return empty('OFF','Looking Glass is hidden');
    if(this.data?.run?.review)return empty('REVIEW','Recorded run · no current forecast is substituted for historical evidence');
    const valid=this.validScenario(),key=this.contractKey(),saved=this.forecastArchive.get(key);
    const current=valid&&(!saved||valid.glass.source_ts>=saved.glass.source_ts)?valid:null;
    const heldInspection=!ignoreViewport&&!this.follow?this.inspectionForecast:null;
    const comparison=this.resonance?.key===key?this.resonance.view:null;
    const chosen=this.forecastPinned?this.pinnedForecast:(heldInspection||current||saved||comparison||this.lastForecast);
    const frozen=Boolean(this.forecastPinned||heldInspection);
    if(!chosen?.glass)return empty('UNAVAILABLE',chosen?.reason||this.data?.looking_glass?.reason||'Waiting for a valid issued Looking Glass path');
    const glass=chosen.glass,horizon=this.scenarioHorizon(glass),now=typeof this.sourceClock==='function'?this.sourceClock():this.data?.server_now;
    if(!horizon)return empty('UNAVAILABLE','Invalid issued forecast horizon');
    const sameContract=glass.ticker===this.data?.market?.ticker&&glass.close_ts===this.data?.market?.close_ts;
    const fixedComparison=chosen.frozen_comparison===true;
    const sameIssue=fixedComparison?sameContract:current&&current.glass.source_ts===glass.source_ts;
    const sourceFresh=this.data?.run?.fresh===true&&!this.data?.run?.stopped&&this.data?.market?.fresh===true&&
      (typeof this.sourceConnected!=='function'||this.sourceConnected())&&Number.isFinite(now)&&
      (fixedComparison?Number.isFinite(this.data.market.time)&&now>=this.data.market.time&&
        now-this.data.market.time<=3:now>=glass.source_ts&&now<=glass.valid_until);
    const inspecting=!ignoreViewport&&(!this.follow||this.reviewMode||this.selected);
    let status,reason;
    const stamp=this.clock(glass.source_ts,true)+' ET',contract=glass.ticker;
    if(Number.isFinite(now)&&now>=horizon.end){status='EXPIRED';reason=`${horizon.rolling?'Forecast horizon ended':'Expired '+contract} · issued ${stamp} · retained at original coordinates`;}
    else if(!sourceFresh){status='STALE';reason=`Stale source · issued ${stamp} · retained for inspection, not live`;}
    else if(this.forecastPinned){status='PINNED';reason=`Pinned ${contract} · issued ${stamp} · later updates do not move these paths`;}
    else if(!sameContract||!sameIssue){status='RETAINED';reason=`Retained ${contract} · issued ${stamp} · awaiting a matching current forecast`;}
    else if(inspecting){status='INSPECTING';reason=`Inspecting issued ${stamp} paths at their original times · not an entry-time forecast`;}
    else{status=glass.status;reason=fixedComparison?
      'Fixed historical shapes compared with observed BTC at matching elapsed times; brightness is historical agreement, not probability':
      horizon.rolling?'Conditional BTC/EMA9 paths through a rolling 15-minute horizon; contract rollover does not end the physical path':'Conditional paths, bounded by this contract close';}
    const retained=!['READY','PARTIAL'].includes(status);
    const pattern=chosen.displayActive||chosen.active;
    const active=!fixedComparison&&!retained&&pattern&&now<pattern.horizon_ts?pattern:null;
    let feature=frozen?chosen.featured:null;
    if(!frozen){
      if(active)feature=this.featureFromView({...chosen,active},this.data);
      else{
        const candidates=[this.lastFeaturedForecast,...(current?.issuedSamples||[]).map(sample=>this.featureFromIssued(sample))]
          .filter(item=>item&&item.run_id===this.runKey());
        feature=candidates.sort((a,b)=>b.source_ts-a.source_ts)[0]||null;
      }
    }
    if(feature){
      const fresh=Boolean(active&&sourceFresh&&feature.source_ts===glass.source_ts&&feature.pattern.key===active.key&&
        feature.path.id===active.path_id&&feature.continuity_generation===active.continuity_generation&&now<feature.horizon_ts);
      const featureStatus=now>=feature.issue_horizon_ts?'EXPIRED':now>=feature.horizon_ts?'ENDED':fresh?'CURRENT':
        this.forecastPinned?'PINNED':inspecting?'INSPECTING':!sourceFresh?'STALE':'RETAINED';
      feature={...feature,status:featureStatus,retained:!fresh,fresh,
        reason:fresh?(feature.original_reason||'Current conditional feature; brightness is not confidence.'):
          `${featureStatus} · issued ${this.clock(feature.source_ts,true)} ET · original shape ends ${this.clock(feature.horizon_ts,true)} ET; not a current forecast`};
    }
    let reference=null,referenceReason=null;
    if(!this.hasForwardSegment(feature)){
      const selected=(frozen||fixedComparison)?{reference:chosen.reference,reason:chosen.referenceReason}:this.referenceFromView(chosen);
      reference=selected.reference;referenceReason=selected.reason||null;
      if(reference){
        const currentIssue=Boolean(!frozen&&sameContract&&sameIssue&&!retained),
          verified=reference.history_verified_at_issue===true,
          referenceStatus=now>=reference.issue_horizon_ts?'EXPIRED':now>=reference.horizon_ts?'ENDED':
            !sourceFresh?'STALE':this.forecastPinned?'PINNED':inspecting?'INSPECTING':
            !currentIssue?'RETAINED':verified?'REFERENCE':'HISTORY_UNVERIFIED';
        reference={...reference,status:referenceStatus,current_issue:currentIssue,source_fresh:sourceFresh,
          fresh:currentIssue&&verified&&sourceFresh,retained:!currentIssue||!sourceFresh,
          reason:reference.original_reason+' '+(verified?'Physical history was verified at issue.':
            'History unverified at issue ('+reference.physical_status_at_issue+'); engine pattern unavailable.')};
      }
    }
    return {status,reason,paths:chosen.paths,glass,retained,active,featured:feature,reference,referenceReason,
      frozen_comparison:fixedComparison,
      comparison_pending:glass.kind==='HISTORICAL_COMPARISON'&&!fixedComparison&&!this.comparisonEligible(chosen),
      current_observation:this.data?.market?.ema_context||null,
      observedPath:frozen&&chosen.observedPath?chosen.observedPath:
        this.resonance?.issue===glass.source_ts&&this.resonance?.key===this.contractKey()?this.observedComparisonPath():null,
      earlierTrails:frozen?chosen.earlierTrails:null,
      physicalHealth:chosen.physicalHealth,
      displayActive:pattern,issued:chosen.issued,issue_ts:glass.source_ts,horizon_ts:horizon.end,rolling:horizon.rolling,
      targetContext:frozen?chosen.targetContext:this.currentTargetContext(),calendar_close_ts:frozen?chosen.calendar_close_ts:this.data?.market?.close_ts};
  }
  resetRoute(){
    this.route={lastTime:-Infinity,lastBar:null,mode:null,high:null,low:null,candidate:null,
      opposite:null,reversalCount:0,ranges:[],pivots:[],segment:0};
  }
  updateRoute(data){
    // This is a causal display annotation, never an entry signal. A completed
    // source bar can confirm an earlier extreme; only the unfinished tail can
    // move. Sampled/incomplete candles cannot confirm a historical turn.
    const route=this.route,now=data?.server_now;
    const bars=(data?.candles||[]).filter(b=>b.complete===true&&b.quality!=='sampled'&&
      [b.time,b.open,b.high,b.low,b.close].every(Number.isFinite)&&b.low>0&&b.high>=b.low&&
      b.open>=b.low&&b.open<=b.high&&b.close>=b.low&&b.close<=b.high&&
      (!Number.isFinite(now)||(b.time+60<=now&&(!Number.isFinite(b.known_at)||b.known_at<=now)))).sort((a,b)=>a.time-b.time);
    const extreme=(bar,kind)=>({time:bar.time,price:kind==='HIGH'?bar.high:bar.low,kind,source:bar.source||bar.quality});
    const confirm=(point,bar)=>{
      const previous=route.pivots.at(-1);
      if(!previous||point.time>previous.time)route.pivots.push({...point,
        confirmedAt:Math.max(bar.time+60,Number.isFinite(bar.known_at)?bar.known_at:bar.time+60),segment:route.segment});
      if(route.pivots.length>500)route.pivots.splice(0,route.pivots.length-500);
    };
    for(const bar of bars){
      if(bar.time<=route.lastTime)continue;
      if(route.lastBar&&bar.time-route.lastTime>90){
        route.segment++;route.mode=null;route.high=null;route.low=null;route.candidate=null;
        route.opposite=null;route.reversalCount=0;route.ranges=[];route.lastBar=null;
      }
      const previous=route.lastBar;
      route.ranges.push(Math.max(bar.high-bar.low,previous?Math.abs(bar.high-previous.close):0,previous?Math.abs(bar.low-previous.close):0));
      if(route.ranges.length>20)route.ranges.shift();
      const threshold=Math.max(bar.close*.00008,route.ranges.reduce((sum,v)=>sum+v,0)/route.ranges.length*1.25);
      if(route.mode===null){
        if(!route.high||bar.high>route.high.price)route.high=extreme(bar,'HIGH');
        if(!route.low||bar.low<route.low.price)route.low=extreme(bar,'LOW');
        if(route.high.time>route.low.time&&bar.close-route.low.price>=threshold){
          confirm(route.low,bar);route.mode='UP';route.candidate=route.high;route.opposite=extreme(bar,'LOW');
        }else if(route.low.time>route.high.time&&route.high.price-bar.close>=threshold){
          confirm(route.high,bar);route.mode='DOWN';route.candidate=route.low;route.opposite=extreme(bar,'HIGH');
        }
      }else{
        const up=route.mode==='UP',price=up?bar.high:bar.low,kind=up?'HIGH':'LOW',other=up?'LOW':'HIGH';
        if(up?price>route.candidate.price:price<route.candidate.price){
          route.candidate=extreme(bar,kind);route.opposite=extreme(bar,other);route.reversalCount=0;
        }else{
          const oppositePrice=up?bar.low:bar.high;
          if(!route.opposite||(up?oppositePrice<route.opposite.price:oppositePrice>route.opposite.price))route.opposite=extreme(bar,other);
          const reversing=previous&&(up?bar.close<previous.close:bar.close>previous.close);
          route.reversalCount=reversing?route.reversalCount+1:0;
          const distance=up?route.candidate.price-bar.close:bar.close-route.candidate.price;
          if(route.reversalCount>=2&&distance>=threshold&&bar.time>route.candidate.time){
            confirm(route.candidate,bar);route.mode=up?'DOWN':'UP';route.candidate=route.opposite;
            route.opposite=extreme(bar,kind);route.reversalCount=0;
          }
        }
      }
      route.lastTime=bar.time;route.lastBar={...bar};
    }
  }
  routeView(){
    const route=this.route,last=route.pivots.at(-1),tail=[];
    if(last&&last.segment===route.segment)tail.push({...last});
    if(route.candidate&&(!last||route.candidate.time>last.time))tail.push({...route.candidate});
    const bar=this.data?.candles?.at(-1);
    if(bar&&Number.isFinite(bar.time)&&Number.isFinite(bar.close)&&bar.close>0&&
       bar.time-route.lastTime<=90&&(!tail.length||bar.time>=tail.at(-1).time))tail.push({time:bar.time,price:bar.close});
    return {pivots:route.pivots.map(p=>({...p})),tail,execution_authority:false};
  }
  physicalLegGuide(view=this.scenarioView()){
    // DISPLAY ONLY: actual certified-candle path + clearly conditional slope
    // extension. This is not an engine pattern, an order signal, or a future TP.
    if(!this.showLookingGlass||!this.follow||this.forecastPinned||this.reviewMode||this.selected||
       this.data?.run?.review||this.data?.run?.stopped||this.data?.run?.fresh!==true||
       this.data?.market?.fresh!==true||
       (typeof this.sourceConnected==='function'&&!this.sourceConnected())||
       !view?.glass||view.retained||!this.data?.candles?.length)return null;
    const market=this.data.market,now=typeof this.sourceClock==='function'?
      this.sourceClock():this.data.server_now;
    if(![market?.time,market?.btc,market?.target,now].every(Number.isFinite)||
       market.btc<=0||market.target<=0||market.time>now+1||now-market.time>3)return null;
    const direction=this.route?.mode==='DOWN'?-1:this.route?.mode==='UP'?1:0;
    if(!direction)return null;
    const pivot=this.route.pivots.filter(point=>point.segment===this.route.segment).at(-1);
    if(!pivot||pivot.kind!==(direction<0?'HIGH':'LOW')||
       ![pivot.time,pivot.price,pivot.confirmedAt].every(Number.isFinite)||
       pivot.confirmedAt>now||pivot.time>=market.time||market.time-pivot.time>2700||
       direction*(market.btc-pivot.price)<=0)return null;
    const bars=(this.data.candles||[]).filter(bar=>bar.complete===true&&bar.quality!=='sampled'&&
      Number.isFinite(bar.time)&&Number.isFinite(bar.close)&&bar.close>0&&
      bar.time>=pivot.time&&bar.time+60<=market.time+2&&
      (!Number.isFinite(bar.known_at)||bar.known_at<=now)).sort((a,b)=>a.time-b.time);
    if(bars.length<3||market.time-(bars.at(-1).time+60)>120)return null;
    if(bars.some((bar,i)=>i>0&&bar.time-bars[i-1].time>120))return null;
    const observed=[{time:pivot.time,btc:pivot.price,source:'CERTIFIED_EXTREME'}];
    for(const bar of bars){
      const time=bar.time+60;
      if(time>observed.at(-1).time)observed.push({time,btc:bar.close,source:'CERTIFIED_CLOSE'});
    }
    if(market.time>observed.at(-1).time)observed.push({time:market.time,btc:market.btc,source:'LIVE_OBSERVATION'});
    else if(Math.abs(market.time-observed.at(-1).time)<=2)observed[observed.length-1]={time:market.time,btc:market.btc,source:'LIVE_OBSERVATION'};
    else return null;
    const window=this.forecastWindow(),start=window.start;
    if(!Number.isFinite(start)||Math.abs(market.time-start)>10||window.end<=start)return null;
    const fullRate=(market.btc-pivot.price)/(market.time-pivot.time);
    const recent=observed.find(point=>point.time>=market.time-240)||observed.at(-2);
    const recentRate=(market.btc-recent.btc)/Math.max(1,market.time-recent.time);
    // An opposing short-term turn suspends the projected part; the observed
    // descending (or ascending) route remains visible without claiming a trend.
    const projected=direction*recentRate>0&&direction*fullRate>0;
    const rate=projected?direction*Math.min(Math.abs(fullRate)*2,
      Math.max(Math.abs(fullRate)*.55,Math.abs(fullRate)*.65+Math.abs(recentRate)*.35)):0;
    const projectedPoints=projected?[{time:start,btc:market.btc},
      {time:start+(window.end-start)*.35,btc:market.btc+rate*(window.end-start)*.35},
      {time:window.end,btc:market.btc+rate*(window.end-start)}]:[];
    const secondsToTarget=projected&&(market.target-market.btc)/rate;
    const crossing=Number.isFinite(secondsToTarget)&&secondsToTarget>0&&
      secondsToTarget<=window.end-start?{time:start+secondsToTarget,btc:market.target,
        beforeContractClose:start+secondsToTarget<=market.close_ts}:null;
    return {direction,pivot,observed,projectedPoints,crossing,target:market.target,
      lastObserved:market.btc,source_time:market.time,conditional:true,execution_authority:false};
  }
  drawObservedLegGuide(guide){
    if(!guide?.observed?.length)return;
    const c=this.ctx,shade=guide.direction<0?'#ffae62':'#5ee3d0';
    c.save();c.beginPath();c.strokeStyle=shade;c.lineWidth=3.1;c.setLineDash([]);
    c.globalAlpha=.86;c.shadowColor=shade;c.shadowBlur=8;
    guide.observed.forEach((point,index)=>{
      const x=this.x(point.time),y=this.y(point.btc);
      if(index===0)c.moveTo(x,y);else c.lineTo(x,y);
    });c.stroke();c.shadowBlur=0;c.restore();
  }
  drawProjectedLegGuide(guide){
    if(!guide?.projectedPoints?.length)return;
    const c=this.ctx,shade=guide.direction<0?'#ffae62':'#5ee3d0';
    const animate=this.liveLegPulseEligible(guide),clock=typeof performance!=='undefined'&&
      typeof performance.now==='function'?performance.now():Date.now();
    const phase=animate ? .5+.5*Math.sin(clock*Math.PI*2/2900) : 0;
    c.save();c.strokeStyle=shade;c.lineWidth=animate?2.9+.7*phase:3;
    c.globalAlpha=animate ? .77+.23*phase : .90;c.shadowColor=shade;c.shadowBlur=animate?3+6*phase:0;
    c.setLineDash([8,5]);c.beginPath();
    for(const [i,point] of guide.projectedPoints.entries()){
      const x=this.forecastX(point.time),y=this.dockY(point.btc);
      if(i===0)c.moveTo(x,y);else c.lineTo(x,y);
    }c.stroke();c.restore();
    if(guide.crossing){
      const x=this.forecastX(guide.crossing.time),y=this.dockY(guide.crossing.btc);
      if(y>=this.top+12&&y<=this.mainBottom-12){
        c.save();c.strokeStyle=shade;c.lineWidth=1.8;c.setLineDash([]);c.beginPath();
        c.arc(x,y,5,0,Math.PI*2);c.stroke();c.restore();
        this.text(guide.crossing.beforeContractClose?'TP CROSS · CONDITIONAL':'TP LEVEL · AFTER ROLLOVER',
          Math.min(this.plotRight-10,x+8),Math.max(this.top+16,y-10),shade,8,'right');
      }
    }
  }
  liveLegPulseEligible(guide){
    return Boolean(guide?.projectedPoints?.length&&this.showLookingGlass&&this.follow&&
      !this.forecastPinned&&!this.reviewMode&&!this.selected&&!this.data?.run?.review&&
      !(typeof document!=='undefined'&&(document.hidden===true||document.visibilityState==='hidden'))&&
      !this.motionPreference?.matches);
  }
  projectedPathOpposesGuide(path,guide){
    const points=path?.points||[];
    if(!guide||points.length<2)return false;
    const first=points[0],last=points.at(-1);
    return Number.isFinite(first.btc)&&Number.isFinite(last.btc)&&
      guide.direction*(last.btc-first.btc)<0;
  }
  drawRoute(){
    const view=this.routeView(),c=this.ctx;
    if(!view.pivots.length)return;
    c.save();c.strokeStyle='#e7e2b7b8';c.lineWidth=1.6;c.shadowColor='#c8d9b944';c.shadowBlur=4;c.setLineDash([]);c.beginPath();
    let previous=null;
    for(const point of view.pivots){const x=this.x(point.time),y=this.y(point.price);
      if(!previous||previous.segment!==point.segment)c.moveTo(x,y);else c.lineTo(x,y);previous=point;}
    c.stroke();c.shadowBlur=0;
    for(const point of view.pivots){const x=this.x(point.time),y=this.y(point.price);if(x<this.left||x>this.historyPlotRight)continue;
      c.beginPath();c.fillStyle='#0b1c25';c.strokeStyle='#dce7c8';c.lineWidth=1.2;c.arc(x,y,2.8,0,Math.PI*2);c.fill();c.stroke();}
    c.beginPath();c.strokeStyle='#e7e2b78c';c.lineWidth=1.4;c.setLineDash([4,5]);
    view.tail.forEach((point,index)=>{const x=this.x(point.time),y=this.y(point.price);if(index===0)c.moveTo(x,y);else c.lineTo(x,y);});
    c.stroke();c.setLineDash([]);c.restore();
  }
  observedEdgeView(){
    const edge=this.data?.observed_edge,point=edge?.display_point;
    if(edge?.kind!=='CAUSAL_EDGE_RETURN_V1'||edge.execution_authority!==false||!edge.edge_id||
       !['YES','NO'].includes(edge.side)||![point?.time,point?.price,point?.known_at,edge.evaluated_at].every(Number.isFinite)||
       point.price<=0||point.time+60>point.known_at||point.known_at>edge.evaluated_at)return null;
    const now=typeof this.sourceClock==='function'?this.sourceClock():this.data?.server_now;
    const current=edge.current===true&&edge.source_valid===true&&this.data?.run?.fresh===true&&!this.data.run.stopped&&
      (typeof this.sourceConnected!=='function'||this.sourceConnected())&&Number.isFinite(now)&&
      Number.isFinite(edge.valid_until)&&edge.evaluated_at<=now&&now<=edge.valid_until;
    return {edge,point,current};
  }
  drawObservedEdge(){
    const view=this.observedEdgeView();if(!view)return;
    const {edge,point,current}=view,c=this.ctx,x=this.x(point.time),y=this.y(point.price);
    const inView=x>=this.left&&x<=this.historyPlotRight&&y>=this.top&&y<=this.mainBottom;
    const color=current?'#9bd9ef':'#7997a3';
    c.save();
    if(inView){c.beginPath();c.strokeStyle=color;c.lineWidth=1.8;c.setLineDash(current?[]:[2,2]);c.arc(x,y,5,0,Math.PI*2);c.stroke();c.setLineDash([]);}
    const first=(current?'OBSERVED ':'RECORDED ')+edge.side+' EDGE · '+String(edge.state||'OBSERVED').replaceAll('_',' ');
    const second=(inView?'':'Outside this view · ')+this.clock(point.time)+' '+(point.kind||'EXTREME')+
      ' · known '+this.clock(point.known_at,true);
    const width=Math.min(this.historyW-16,Math.max(180,...[first,second].map(t=>{
      const measured=c.measureText?.(t)?.width;return (Number.isFinite(measured)?measured:t.length*5.2)+16;
    })));
    const xx=this.left+8,yy=this.top+4,maxChars=Math.max(8,Math.floor((width-12)/5.2));
    c.fillStyle='#08151feb';c.fillRect(xx,yy,width,32);
    this.text(first.slice(0,maxChars),xx+6,yy+12,color,9);
    this.text(second.slice(0,maxChars),xx+6,yy+25,'#829da9',8);
    c.restore();
  }
  candleRange(bars,from,end){
    const values=bars.flatMap(b=>[b.low,b.high]).filter(v=>Number.isFinite(v)&&v>0);
    // Target inclusion is an explicit user action. Neither projected extrema,
    // EMA extrapolations, nor binary-contract quotes determine this scale.
    if(this.fitTarget)(this.data.targets||[]).filter(t=>t.start_ts<end&&(t.close_ts??end)>from&&Number.isFinite(t.target)&&t.target>0).forEach(t=>values.push(t.target));
    if(!values.length)return null;
    const low=Math.min(...values),high=Math.max(...values),padding=Math.max(low*.00005,(high-low)*.07);
    return {low:Math.max(1e-10,low-padding),high:high+padding};
  }
  requestDraw(){
    if(this.destroyed||this.raf)return;
    this.raf=1;const handle=requestAnimationFrame(()=>{this.raf=0;this.draw();});
    if(this.raf)this.raf=handle||1;
  }
  featuredPulseEligible(view=this.scenarioView()){
    return Boolean(view?.featured?.fresh&&view.active&&this.showLookingGlass&&this.follow&&!this.forecastPinned&&
      !this.reviewMode&&!this.selected&&!this.data?.run?.review&&
      !(typeof document!=='undefined'&&(document.hidden===true||document.visibilityState==='hidden'))&&
      !this.motionPreference?.matches);
  }
  scheduleFeaturedPulse(view){
    if(!this.featuredPulseEligible(view)&&!this.liveLegPulseEligible(this.currentGuide)){
      if(this.pulseTimer!==null&&typeof clearTimeout==='function')clearTimeout(this.pulseTimer);
      this.pulseTimer=null;return;
    }
    if(this.pulseTimer===null&&typeof setTimeout==='function'){
      this.pulseTimer=setTimeout(()=>{this.pulseTimer=null;this.requestDraw();},1000/15);
      this.pulseTimer?.unref?.();
    }
  }
  localPoint(e){const r=this.canvas.getBoundingClientRect();return{x:e.clientX-r.left,y:e.clientY-r.top};}
  down(e){
    const point=this.localPoint(e);
    if(point.x>=this.dockLeft&&point.x<=this.plotRight&&Math.abs(point.y-this.divider)>=7){this.canvas.focus();return;}
    if(e.pointerType==='touch'){
      this.touches.set(e.pointerId,point);
      this.canvas.setPointerCapture(e.pointerId);
      if(this.touches.size===2){const [a,b]=[...this.touches.values()],mid=(a.x+b.x)/2;
        const span=this.viewSpan();this.pinch={distance:Math.max(1,Math.hypot(a.x-b.x,a.y-b.y)),span,anchor:this.end-span+(mid-this.left)/this.historyW*span};
        this.drag=null;this.freezeViewport();this.tooltip.classList.add('hidden');return;
      }
      if(this.touches.size>2)return;
    }
    if(e.button!==0)return;const p=point;this.canvas.focus();this.canvas.setPointerCapture(e.pointerId);
    const axis=this.priceAxisAt(p.x);let mode=axis?'scale':'pan';
    if(Math.abs(p.y-this.divider)<7)mode='divider';
    const range=this.range;
    this.drag={...p,end:this.end,span:this.viewSpan(),mode,moved:false,range:range?{...range}:null};}
  move(e){const p=this.localPoint(e);this.pointer=p;
    if(e.pointerType==='touch'&&this.touches.has(e.pointerId)){
      this.touches.set(e.pointerId,p);
      if(this.pinch&&this.touches.size>=2){const [a,b]=[...this.touches.values()],mid=(a.x+b.x)/2;
        this.span=Math.max(300,Math.min(64800,this.pinch.span*this.pinch.distance/Math.max(1,Math.hypot(a.x-b.x,a.y-b.y))));
        this.viewportSpan=this.span;
        this.end=this.pinch.anchor+(1-(mid-this.left)/this.historyW)*this.span;
        this.manualY=null;this.saveSpan();this.requestDraw();return;
      }
    }
    if(this.drag){const d=this.drag;d.moved=d.moved||Math.abs(p.x-d.x)+Math.abs(p.y-d.y)>4;
      if(d.mode==='scale'&&d.range){const mid=(d.range.high+d.range.low)/2,half=(d.range.high-d.range.low)/2*Math.exp((p.y-d.y)/110);this.manualY={low:Math.max(1e-10,mid-half),high:mid+half};}
      else if(d.mode==='divider'){this.ratio=Math.max(.5,Math.min(.87,p.y/Math.max(200,this.h)));}
      else{if(this.follow)this.freezeViewport();this.viewportSpan=d.span;this.end=d.end-(p.x-d.x)*d.span/this.historyW;}
      this.tooltip.classList.add('hidden');
    }
    this.canvas.style.cursor=this.drag?'grabbing':this.priceAxisAt(p.x)?'ns-resize':Math.abs(p.y-this.divider)<7?'row-resize':'crosshair';this.requestDraw();
  }
  up(e){
    if(e.pointerType==='touch'&&this.pinch){this.touches.delete(e.pointerId);if(!this.touches.size)this.pinch=null;this.drag=null;try{this.canvas.releasePointerCapture(e.pointerId);}catch(_){}this.requestDraw();return;}
    this.touches.delete(e.pointerId);
    if(this.drag&&!this.drag.moved&&this.drag.mode==='pan'){const near=this.tradeMarkerAt(this.localPoint(e),20);if(near)this.onSelect?.(near.trade);}
    this.drag=null;try{this.canvas.releasePointerCapture(e.pointerId);}catch(e){}this.requestDraw();}
  cancelPointer(e){this.touches.delete(e.pointerId);if(!this.touches.size)this.pinch=null;this.drag=null;this.pointer=null;this.tooltip.classList.add('hidden');this.requestDraw();}
  wheel(e){e.preventDefault();const p=this.localPoint(e),axis=this.priceAxisAt(p.x);
    if(axis){const r=this.manualY||this.range;
      if(r){const mid=(r.low+r.high)/2,half=(r.high-r.low)/2*Math.exp(e.deltaY*.002),next={low:Math.max(1e-10,mid-half),high:mid+half};
        this.manualY=next;}}
    else if(p.x<this.historyPlotRight){const old=this.follow?this.span:this.viewSpan(),f=(Math.max(0,Math.min(this.historyW,p.x-this.left)))/this.historyW;const anchor=this.end-this.viewSpan()+f*this.viewSpan();this.span=Math.max(300,Math.min(64800,old*Math.exp(e.deltaY*.0015)));this.viewportSpan=this.span;if(this.follow)this.syncLiveViewport();else this.end=anchor+(1-f)*this.span;this.saveSpan();this.manualY=null;}this.requestDraw();}
  x(t){return this.left+(t-(this.end-this.viewSpan()))/this.viewSpan()*this.historyW;}
  historyTimeAt(x){return this.end-this.viewSpan()+(x-this.left)/this.historyW*this.viewSpan();}
  forecastX(t){const window=this.forecastWindow();return this.dockLeft+(t-window.start)/window.seconds*this.forecastW;}
  forecastTimeAt(x){const window=this.forecastWindow();return window.start+(x-this.dockLeft)/this.forecastW*window.seconds;}
  y(v){return this.top+(this.range.high-v)/(this.range.high-this.range.low)*(this.mainBottom-this.top);}
  dockPlotTop(){return this.top+Math.min(134,Math.max(0,this.mainBottom-this.top-100));}
  dockY(v){return this.y(v);}
  dockPriceAt(y){const range=this.range;return range?
    range.high-(y-this.top)/(this.mainBottom-this.top)*(range.high-range.low):NaN;}
  priceAxisAt(x){
    if(x>this.w-this.priceAxisW)return 'history';
    return null;
  }
  qy(v){return this.quoteBottom-v*(this.quoteBottom-this.quoteTop);}
  clock(t,seconds=false){return new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',hour:'2-digit',minute:'2-digit',...(seconds?{second:'2-digit'}:{}),hour12:false}).format(new Date(t*1000));}
  price(v,d=2){const asset=this.data?.asset?.symbol;const decimals=asset==='DOGE'?6:asset==='XRP'?4:d;return Number.isFinite(v)?v.toLocaleString('en-US',{minimumFractionDigits:decimals,maximumFractionDigits:decimals}):'—';}
  text(s,x,y,color='#7897a9',size=10,align='left'){const c=this.ctx;c.fillStyle=color;c.font=`${size*this.fontScale}px "Segoe UI",sans-serif`;c.textAlign=align;c.fillText(s,x,y);c.textAlign='left';}
  line(x1,y1,x2,y2,color,width=1,dash=[]){const c=this.ctx;c.beginPath();c.strokeStyle=color;c.lineWidth=width;c.setLineDash(dash);c.moveTo(x1,y1);c.lineTo(x2,y2);c.stroke();c.setLineDash([]);}
  badge(s,y,color){const c=this.ctx,right=this.w;
    const width=this.priceAxisW-2,height=20*this.fontScale;
    const yy=Math.max(this.top+height/2,Math.min(this.mainBottom-height/2,y));
    c.fillStyle=color;c.fillRect(right-width,yy-height/2,width,height);
    this.text(s,right-5,yy+3*this.fontScale,'#07141c',10,'right');}
  priceTicks(range){
    if(!range||!Number.isFinite(range.low)||!Number.isFinite(range.high)||range.high<=range.low)return {step:1,values:[]};
    const raw=(range.high-range.low)/6,mag=10**Math.floor(Math.log10(raw));
    const step=([1,2,2.5,5,10].find(value=>value*mag>=raw)||10)*mag,values=[];
    for(let value=Math.ceil(range.low/step)*step;value<=range.high;value+=step)values.push(value);
    return {step,values};
  }
  layoutPriceAxis(ticks){
    // Measure the actual native precision (including XRP/DOGE) at the current
    // TV/phone font size. Short SOL labels need no BTC-sized empty column.
    const c=this.ctx,market=this.data?.market||{},labels=[
      [(this.data?.asset?.symbol||'BTC')+' $',8],['1.00',9],
      ...ticks.values.map(value=>[this.price(value,ticks.step<1?2:0),10])
    ];
    if(Number.isFinite(market.btc)&&market.time>=this.end-this.viewSpan()&&market.time<=this.end)
      labels.push([this.price(market.btc),10]);
    c.save();
    const measured=Math.max(...labels.map(([label,size])=>{
      c.font=`${size*this.fontScale}px "Segoe UI",sans-serif`;
      const width=c.measureText(label).width;
      return Number.isFinite(width)?width:label.length*size*this.fontScale*.6;
    }));
    c.restore();
    this.priceAxisW=Math.max(34,Math.ceil(measured+10));
    this.plotRight=this.w-this.priceAxisW-1;this.plotW=this.plotRight-this.left;
    // Keep the observed-history width and its time mapping unchanged. Every
    // pixel recovered from the former fixed gutter belongs to Looking Glass.
    const formerAxisW=Math.max(74,Math.ceil(74*this.fontScale)),
      historyPaneW=Math.min((this.w-this.left-formerAxisW-1)*(1-this.forecastFraction),this.plotW-40);
    this.dockLeft=this.left+historyPaneW;this.forecastW=this.plotRight-this.dockLeft;
    this.historyAxisW=0;this.historyPlotRight=this.dockLeft;
    // A full candle still fits before the independent future pane begins.
    this.historyW=this.historyPlotRight-this.left-14;
    this.historyDataRight=this.left+this.historyW;
  }
  featuredPriceVisibility(feature){
    if(!feature)return null;
    const window=this.forecastWindow(),points=feature.path.points,values=[];
    for(let i=1;i<points.length;i++){
      const a=points[i-1],b=points[i],start=Math.max(a.time,window.start),end=Math.min(b.time,window.end);
      if(end<start)continue;
      for(const time of [start,end])values.push(a.btc+(b.btc-a.btc)*(time-a.time)/(b.time-a.time));
    }
    if(!values.length)return feature.horizon_ts<=window.start?'FEATURE ENDED':'FEATURE OUTSIDE TIME VIEW';
    if(this.dockRange&&(Math.min(...values)>this.dockRange.high||Math.max(...values)<this.dockRange.low))return 'FEATURE OUTSIDE PRICE VIEW';
    return null;
  }
  traceHistorical(path,field,map,color,width,alpha,dash=[],mapY=value=>this.y(value)){
    const c=this.ctx;c.save();c.beginPath();c.strokeStyle=color;c.lineWidth=width;
    c.globalAlpha=alpha;c.setLineDash(dash);let begun=false;
    for(const point of path.points||[]){
      if(!Number.isFinite(point.time)||!Number.isFinite(point[field])){begun=false;continue;}
      const x=map(point.time),y=mapY(point[field]);
      if(!begun){c.moveTo(x,y);begun=true;}else c.lineTo(x,y);
    }
    c.stroke();c.restore();
  }
  observedComparisonPath(){
    const r=this.resonance,points=(r?.observations||[]).map(point=>({...point}));
    const market=this.data?.market;
    if(r?.key===this.contractKey()&&market?.fresh===true&&this.data?.run?.fresh===true&&
       !this.data.run.stopped&&Number.isFinite(market.time)&&Number.isFinite(market.btc)&&
       (!Number.isFinite(this.data.server_now)||market.time<=this.data.server_now)&&
       market.time>=r.issue&&market.time<r.close&&market.time>(points.at(-1)?.time??-Infinity))
      points.push({time:market.time,btc:market.btc});
    return {points};
  }
  pathInDock(path,field='btc',window=this.forecastWindow()){
    return (path?.points||[]).some((point,i,points)=>i>0&&
      [point.time,point[field],points[i-1].time,points[i-1][field]].every(Number.isFinite)&&
      point.time>points[i-1].time&&
      Math.max(points[i-1].time,window.start)<Math.min(point.time,window.end));
  }
  dockFanPaths(view){
    if(!this.showLookingGlass||!view?.glass)return [];
    const window=this.forecastWindow(),items=new Map(),issue=view?.glass?.source_ts;
    const add=(path,source,{selected=false,reference=null}={})=>{
      if(!this.pathInDock(path,'btc',window)&&!this.pathInDock(path,'e9',window))return;
      const identity=`${source}|${path.id??this.resonanceIdentity(path)??items.size}`;
      if(items.has(identity))return;
      const original=this.resonance?.paths?.find(item=>this.resonanceIdentity(item)===this.resonanceIdentity(path));
      // A newly reanchored path can share a historical ID with a scored path.
      // Earned emphasis belongs only to the exact original issued vertices.
      const current=source===this.resonance?.issue&&this.resonance?.key===this.contractKey()&&
        original?.points?.length===path.points.length&&path.points.every((point,index)=>
          ['time','btc','e9'].every(field=>point[field]===original.points[index][field]));
      items.set(identity,{path,issue:source,selected,current,archived:!current,reference});
    };
    // The selected issue always gets its own render pass. An unrelated or
    // offscreen archive cannot suppress any of its available alternatives.
    for(const path of view?.paths||[])add(path,issue,{selected:true,
      reference:view.reference?.source_ts===issue&&view.reference.path.id===path.id?view.reference:null});
    if((this.forecastPinned||!this.follow)&&Array.isArray(view?.earlierTrails)){
      for(const item of view.earlierTrails)add(item.path,item.issue);
      return [...items.values()];
    }
    // Keep the current fan clear. Only the best earlier matched trails are
    // overlaid, at their original prices/times, rather than complete old fans.
    if(!this.forecastPinned&&this.follow&&this.resonance?.key===this.contractKey())
      for(const ranked of this.resonanceRanking().filter(item=>item.visits>0).slice(0,2))
        add(ranked.path,this.resonance.issue);
    for(const record of this.resonanceArchive?.values()||[]){
      if(record.run_id!==this.runKey()||record.key===this.resonance?.key)continue;
      if((this.forecastPinned||!this.follow)&&Number.isFinite(issue)&&record.issue>issue)continue;
      // Legacy archives contain no selected-trail list. Their original
      // reference remains a neutral trace, without inventing a match score.
      const keys=Array.isArray(record.trail_keys)?record.trail_keys.slice(0,2):
        record.reference?.path?[this.resonanceIdentity(record.reference.path)]:[];
      for(const path of record.paths||[])if(keys.includes(this.resonanceIdentity(path)))add(path,record.issue);
    }
    return [...items.values()];
  }
  comparisonObservation(view){
    if(view?.observedPath)return view.observedPath;
    return view?.glass?.source_ts===this.resonance?.issue&&this.resonance?.key===this.contractKey()?
      this.observedComparisonPath():{points:[]};
  }
  forecastRange(view=this.scenarioView()){
    const window=this.forecastWindow(),values=[];
    const sample=(path,field)=>{
      const points=path?.points||[];
      for(let i=1;i<points.length;i++){
        const a=points[i-1],b=points[i];
        if(![a.time,b.time,a[field],b[field]].every(Number.isFinite)||b.time<=a.time)continue;
        const start=Math.max(a.time,window.start),end=Math.min(b.time,window.end);
        if(end<start)continue;
        for(const time of [start,end]){
          const value=a[field]+(b[field]-a[field])*(time-a.time)/(b.time-a.time);
          if(value>0)values.push(value);
        }
      }
    };
    for(const item of this.dockFanPaths(view))for(const field of ['btc','e9'])sample(item.path,field);
    for(const item of [view.featured,view.reference,view.issued])
      for(const field of ['btc','e9'])sample(item?.path,field);
    sample(this.comparisonObservation(view),'btc');
    for(const target of this.targetSegments(window.start,window.end))values.push(target.target);
    if(!values.length&&Number.isFinite(view?.glass?.source_ts)){
      const anchor=view?.paths?.[0]?.points?.[0]?.btc;if(Number.isFinite(anchor)&&anchor>0)values.push(anchor);
    }
    if(!values.length)return null;
    const low=Math.min(...values),high=Math.max(...values),padding=Math.max(low*.00005,(high-low)*.09);
    return {low:Math.max(1e-10,low-padding),high:high+padding};
  }
  drawFrozenFans(map,{pane='dock',view,guide}={}){
    // Storage does not imply an overlay on candles. All Looking Glass
    // geometry is clipped by the caller to its independent right-hand pane.
    if(pane!=='dock'||!this.showLookingGlass)return 0;
    const colors={CONTINUATION:'#65c9fa',ROTATION_STALL:'#b7a0ec',REVERSAL:'#edaa65',PATTERN:'#bcffb0'};
    let drawn=0;
    for(const item of this.dockFanPaths(view)){
      const {path,current,reference}=item,style=this.resonanceStyle(path,!current);
      const liveFamily=current||item.selected&&view?.glass?.ticker===this.data?.market?.ticker&&
        view.glass.close_ts===this.data?.market?.close_ts;
      const opposing=this.projectedPathOpposesGuide(path,guide);
      const color=opposing?'#8195a5':liveFamily?(colors[path.family]||'#88adbc'):'#9aacb8';
      // Every supplied alternative retains BTC and dotted EMA9 at a readable
      // baseline. Resonance adds emphasis; it never erases other families.
      if(this.pathInDock(path,'btc')){
        this.traceHistorical(path,'btc',map,color,1.15,opposing?.20:item.selected ? .44 : current ? .30 : .24,[7,5],v=>this.dockY(v));drawn++;
      }
      if(item.selected&&this.pathInDock(path,'e9'))
        this.traceHistorical(path,'e9',map,color,.9,.30,[2,5],v=>this.dockY(v));
      if(current&&style.emphasized&&!reference&&!opposing)this.drawResonance(path,map,color,v=>this.dockY(v));
    }
    const observed=this.comparisonObservation(view);
    if(observed.points?.length>=2){
      this.traceHistorical(observed,'btc',map,'#e4f6ff',2,.95,[],v=>this.dockY(v));
      const last=observed.points.at(-1),c=this.ctx;c.save();c.setLineDash([]);
      c.fillStyle='#e4f6ff';c.beginPath();c.arc(map(last.time),this.dockY(last.btc),3,0,Math.PI*2);c.fill();c.restore();
    }
    return drawn;
  }
  drawLookingGlass(view,guide=null){
    const c=this.ctx,window=this.forecastWindow(),right=this.dockLeft+this.forecastW,feature=view.featured,reference=view.reference;
    const trace=(path,field,map,color,width,dash)=>{
      c.beginPath();c.strokeStyle=color;c.lineWidth=width;c.setLineDash(dash);
      path.points.forEach((point,index)=>{const x=map(point.time),y=this.dockY(point[field]);if(index===0)c.moveTo(x,y);else c.lineTo(x,y);});c.stroke();
    };
    c.save();c.beginPath();c.rect(this.dockLeft,this.top,this.forecastW,this.mainBottom-this.top);c.clip();
    c.fillStyle='#6595ba0b';c.fillRect(this.dockLeft,this.top,this.forecastW,this.mainBottom-this.top);
    this.drawTargetSegments(window.start,window.end,t=>this.forecastX(t),{dock:true});
    this.drawFrozenFans(t=>this.forecastX(t),{pane:'dock',view,guide});
    const observation=this.comparisonObservation(view),cutoff=observation.points?.at(-1)?.time;
    if(Number.isFinite(cutoff)&&cutoff>=window.start&&cutoff<=window.end)
      this.line(this.forecastX(cutoff),this.top,this.forecastX(cutoff),this.mainBottom,'#a4bac766',1,[2,5]);
    if(view.issued&&this.pathInDock(view.issued.path,'btc'))
      trace(view.issued.path,'btc',t=>this.forecastX(t),'#d1e2ef82',1.4,[2,6]);
    if(feature){
      const featureOpposes=this.projectedPathOpposesGuide(feature.path,guide);
      const pulse=!featureOpposes&&this.featuredPulseEligible(view),clock=typeof performance!=='undefined'&&typeof performance.now==='function'?performance.now():Date.now();
      const phase=pulse ? .5+.5*Math.sin(clock/3200*Math.PI*2) : 0;
      c.save();c.shadowColor=featureOpposes?'#899dad':'#ffd65a';c.shadowBlur=pulse?3+4*phase:0;
      c.globalAlpha=featureOpposes ? .24 : pulse ? .84+.16*phase : 1;
      trace(feature.path,'btc',t=>this.forecastX(t),featureOpposes?'#9baebe':'#ffd65a'+(feature.fresh?'ff':'b0'),featureOpposes?1.2:3,[10,5]);
      c.shadowBlur=0;trace(feature.path,'e9',t=>this.forecastX(t),featureOpposes?'#9baebe':'#ffd65a'+(feature.fresh?'b8':'66'),featureOpposes ? .9 : 1.8,[2,5]);
      const point=feature.path.points.at(-1);c.setLineDash([]);c.beginPath();c.strokeStyle=featureOpposes?'#9baebe':'#ffd65a';c.lineWidth=featureOpposes?1:2;
      c.arc(this.forecastX(point.time),this.dockY(point.btc),3.5,0,Math.PI*2);c.stroke();c.restore();
      c.shadowBlur=0;c.globalAlpha=1;
    }
    if(reference){
      // A reference is always static, including fresh verified observations.
      // Motion is reserved for an actual current supported engine feature.
      c.save();c.shadowBlur=0;c.globalAlpha=1;
      const opposes=this.projectedPathOpposesGuide(reference.path,guide);
      c.globalAlpha=opposes ? .24 : 1;
      trace(reference.path,'btc',t=>this.forecastX(t),opposes?'#9baebe':'#ffd65acc',opposes ? 1.2 : 3,[10,5]);
      trace(reference.path,'e9',t=>this.forecastX(t),opposes?'#9baebe':'#ffd65a88',opposes ? .9 : 1.8,[2,5]);
      const point=reference.path.points.at(-1);c.setLineDash([]);c.beginPath();c.strokeStyle='#ffd65acc';c.lineWidth=2;
      c.arc(this.forecastX(point.time),this.dockY(point.btc),3.5,0,Math.PI*2);c.stroke();c.restore();
    }
    // The conditional guide supersedes *visual* brightness, not the supplied
    // historical paths or any trading authority.
    this.drawProjectedLegGuide(guide);
    c.setLineDash([]);
    const boundaries=[...new Set([view.glass?.close_ts,view.calendar_close_ts])].filter(time=>Number.isFinite(time)&&time>=window.start&&time<=window.end);
    for(const time of boundaries){const x=this.forecastX(time);
      this.line(x,this.top,x,this.mainBottom,'#8bb5c18c',1,[3,5]);
      this.text('ROLLOVER '+this.clock(time),Math.min(right-5,Math.max(this.dockLeft+108,x-5)),this.mainBottom-28*this.fontScale,'#8baab8',9,'right');
    }
    if(Number.isFinite(view.horizon_ts)&&view.horizon_ts>=window.start&&view.horizon_ts<=window.end){
      const x=this.forecastX(view.horizon_ts);this.line(x,this.top,x,this.mainBottom,'#6595ba60',1,[2,6]);
      this.text((view.rolling?'HORIZON ':'CLOSE ')+this.clock(view.horizon_ts),Math.min(right-5,Math.max(this.dockLeft+90,x-5)),this.mainBottom-46*this.fontScale,'#668ba1',8,'right');
    }
    const available=this.dockFanPaths(view).filter(item=>item.selected).length;
    const captions=[['Looking Glass · 15 min · shared '+(this.data?.asset?.symbol&&this.data.asset.symbol!=='BTC'?'spot':'BTC')+' scale',13,'#adc6d5',9],
      ['ISSUED '+this.clock(window.start,true)+' ET · '+available+' supplied paths · not probability',28,'#668ba1',8]];
    if(reference){
      captions.push(['REFERENCE · '+reference.label,45,'#ffd65a',9]);
      const history=reference.history_verified_at_issue?'Conditional comparison · not an engine pattern':'HISTORY UNVERIFIED · '+reference.physical_status_at_issue;
      captions.push([history,60,reference.history_verified_at_issue?'#adac92':'#d7bb7e',8]);
      captions.push([(reference.status==='REFERENCE'||reference.status==='HISTORY_UNVERIFIED'?'':reference.status+' · ')+
        'ISSUED '+this.clock(reference.source_ts,true)+' · ENDS '+this.clock(reference.horizon_ts,true)+' ET',
        75,'#94a5a1',8]);
      const offscreen=this.featuredPriceVisibility(reference)?.replace(/^FEATURE/,'REFERENCE');
      if(offscreen)captions.push([offscreen,90,'#d7bb7e',8]);
      if(feature)captions.push(['Last featured '+(feature.status==='ENDED'||feature.status==='EXPIRED'?'ended ':'issued ')+
        this.clock(feature.status==='ENDED'||feature.status==='EXPIRED'?feature.horizon_ts:feature.source_ts,true)+' ET · original retained',
        offscreen?105:90,'#8c9fa7',8]);
    }else if(feature){
      const tag=feature.fresh?'MAIN PATH':feature.status==='EXPIRED'||feature.status==='ENDED'?'FEATURE ENDED':'LAST FEATURED';
      captions.push([tag+' · '+(feature.pattern.label||'Issued path'),45,feature.fresh?'#ffd65a':'#c7b985',9]);
      captions.push([(feature.fresh?'ISSUED ':feature.status+' · ISSUED ')+this.clock(feature.source_ts,true)+' ET',60,'#adac92',8]);
      const offscreen=this.featuredPriceVisibility(feature),finite=feature.horizon_ts<feature.issue_horizon_ts;
      captions.push([(offscreen?offscreen+' · ':finite?'SHAPE ENDS ':'ENDS ')+this.clock(feature.horizon_ts,true)+' ET',75,offscreen?'#d7bb7e':'#94a5a1',8]);
    }else{
      captions.push([view.retained?view.status+' · ISSUED '+this.clock(view.glass.source_ts,true)+' ET':
        view.status==='OFF'?'Looking Glass hidden':view.paths.length?(view.glass?.reason||'Historical analog illustrations · no price predictions'):view.reason||'Waiting for issued paths',45,'#8c9fa7',9]);
      if(view.retained)captions.push(['Original paths · no current featured pattern',60,'#8c9fa7',8]);
      else if(view.paths.length&&view.referenceReason)captions.push([view.referenceReason,60,'#8c9fa7',8]);
    }
    const illuminated=this.resonanceRanking().filter(item=>this.resonanceStyle(item.path).emphasized).length;
    if(this.resonance?.key===this.contractKey()&&view.glass?.source_ts===this.resonance.issue&&illuminated){
      const y=captions.at(-1)[1]+15;
      captions.push([`RESONANCE · best ${illuminated} observed matches`,y,'#65ddc9',8]);
    }
    if(this.comparisonObservation(view).points?.length>=2)
      captions.push(['White = recorded spot · scores reset at rollover',captions.at(-1)[1]+15,'#a4bac7',8]);
    if(view.glass?.kind==='HISTORICAL_COMPARISON'){
      const earlier=this.dockFanPaths(view).filter(item=>!item.selected).length;
      captions.splice(0,captions.length,
        ['Looking Glass · 15 min · shared '+(this.data?.asset?.symbol&&this.data.asset.symbol!=='BTC'?'spot':'BTC')+' scale',13,'#adc6d5',9],
        [(view.retained?view.status:view.comparison_pending?'PREVIEW':'LIVE COMPARISONS')+' · '+
          this.clock(view.glass.source_ts,true)+' ET · '+available+' paths',28,'#8ba8bb',8],
        [reference?'Yellow: '+reference.label:view.comparison_pending?'Waiting for completed EMA9 slope':'No matching yellow reference',43,reference?'#ffd65a':'#c7b88b',8],
        [earlier?'Earlier trails: '+earlier+' · original times / prices':'Historical shapes · not probability',58,'#8ba8bb',8]);
      if(reference&&!reference.history_verified_at_issue)
        captions.push(['History at issue: '+reference.physical_status_at_issue,73,'#d7bb7e',8]);
    }
    if(guide){
      captions.push(['OBSERVED '+(guide.direction<0?'DOWN':'UP')+' LEG · LAST CONFIRMED '+
        (guide.direction<0?'PEAK':'TROUGH'),73,guide.direction<0?'#ffb96e':'#6ce6d8',8]);
      if(guide.projectedPoints.length)
        captions.push(['PULSING DASH = CONDITIONAL · NOT A TRADE SIGNAL',88,'#a3bed2',8]);
    }
    // Embedded rooms render the same provenance in an accessible disclosure
    // outside the canvas. Emit only changed text, not every animation frame.
    const information=captions.map(([text])=>text),informationKey=JSON.stringify([this.data?.asset?.symbol??null,information]);
    if(typeof this.onLookingGlassInfo==='function'&&informationKey!==this.lookingGlassInfoKey){
      this.lookingGlassInfoKey=informationKey;
      this.onLookingGlassInfo(information);
    }
    if(this.showLookingGlassInfo!==false){
      c.save();
      const visibleCaptions=captions.filter(([,offset])=>offset<=this.dockPlotTop()-this.top-6);
      const captionWidth=Math.min(Math.max(0,this.forecastW-8),Math.max(0,...visibleCaptions.map(([text,, ,size])=>{
        c.font=`${size*this.fontScale}px "Segoe UI",sans-serif`;
        const measured=c.measureText(text)?.width;
        return Number.isFinite(measured)?measured:text.length*size*this.fontScale*.6;
      }))+8),captionHeight=Math.max(0,Math.min(this.dockPlotTop()-this.top-2,(visibleCaptions.at(-1)?.[1]||0)+6));
      const anchorY=this.dockY(view.paths?.[0]?.points?.[0]?.btc);
      const captionTop=Number.isFinite(anchorY)&&anchorY<this.top+captionHeight+24?
        Math.max(this.top,this.mainBottom-captionHeight-58):this.top;
      c.fillStyle='#07151ef2';c.fillRect(this.dockLeft+4,captionTop+2,captionWidth,captionHeight);c.restore();
      for(const [text,offset,color,size]of visibleCaptions)this.text(text,this.dockLeft+8,captionTop+offset,color,size);
    }
    c.restore();
    if(this.focusVisual){
      // Explicit rollover boundary: decorative pulse only, never a trading signal.
      c.save();c.shadowColor='#06eafe';c.shadowBlur=17;
      this.line(this.dockLeft,this.top,this.dockLeft,this.quoteBottom,'#64f9ff',3);
      c.restore();
    }else this.line(this.dockLeft,this.top,this.dockLeft,this.quoteBottom,'#527587',1.2);
    // The small axis break makes the two independent horizontal scales visible.
    for(const y of [this.mainBottom+3,this.quoteBottom+3]){
      this.line(this.dockLeft-5,y+3,this.dockLeft-1,y-3,'#9bb8c7',1.4);
      this.line(this.dockLeft+1,y+3,this.dockLeft+5,y-3,'#9bb8c7',1.4);
    }
  }
  emaGapGuides(candles,emas){
    // VISUAL ONLY. An absent Coinbase minute cannot be given an invented
    // close. The official e9/e30 fields stay null until period-SMA warmup
    // completes; these faint dashed traces are an *approximation* through a
    // short source gap, never evidence for the Commander or historical fills.
    // Beyond two missing 1m candles we draw nothing across the blind interval.
    const exact=new Map((emas||[]).filter(p=>Number.isFinite(p.time)).map(p=>[p.time,p]));
    const known={e9:null,e30:null},active={e9:null,e30:null},out=[];
    const completed=(candles||[]).filter(b=>b.complete===true&&Number.isFinite(b.time)&&
      Number.isFinite(b.close)&&b.close>0).slice().sort((a,b)=>a.time-b.time);
    let previous=null;
    for(const bar of completed){
      if(previous){
        const delta=bar.time-previous.time;
        if(delta>60+0.001){
          const missed=Math.round(delta/60)-1;
          for(const field of ['e9','e30']){
            if(missed>=1&&missed<=2&&Number.isFinite(known[field])){
              active[field]={field,points:[{time:previous.time,value:known[field]}],
                missed_minutes:missed,basis:'DISPLAY_ONLY_GAP_ESTIMATE'};
              out.push(active[field]);
            }else active[field]=null;
          }
        }else if(delta<=0){
          for(const field of ['e9','e30'])active[field]=null;
        }
      }
      const official=exact.get(bar.time)||{};
      for(const [field,period] of [['e9',9],['e30',30]]){
        if(Number.isFinite(official[field])){
          known[field]=official[field];active[field]=null;continue;
        }
        const guide=active[field];
        if(guide&&Number.isFinite(known[field])){
          const estimate=known[field]+2/(period+1)*(bar.close-known[field]);
          known[field]=estimate;
          guide.points.push({time:bar.time,value:estimate});
        }
      }
      previous=bar;
    }
    return out.filter(p=>p.points.length>=2);
  }
  drawEmaGapGuides(guides,from,end){
    // Caller has already clipped to the observed-candle pane.
    const c=this.ctx;
    for(const guide of guides){
      c.save();c.strokeStyle=guide.field==='e9'?'#37cede':'#e8ad51';
      c.globalAlpha=.58;c.lineWidth=guide.field==='e9'?1.45:1.2;
      c.setLineDash([3,4]);c.beginPath();let started=false;
      for(const point of guide.points){
        if(!Number.isFinite(point.value)||!Number.isFinite(point.time))continue;
        const x=this.x(point.time),y=this.y(point.value);
        if(!Number.isFinite(y)){started=false;continue;}
        if(!started){c.moveTo(x,y);started=true;}else c.lineTo(x,y);
      }
      c.stroke();c.restore();
    }
  }
  draw(){
    const r=this.canvas.parentElement.getBoundingClientRect();this.w=Math.max(1,Math.floor(r.width));this.h=Math.max(1,Math.floor(r.height));const dpr=window.devicePixelRatio||1;
    if(this.canvas.width!==Math.round(this.w*dpr)||this.canvas.height!==Math.round(this.h*dpr)){this.canvas.width=Math.round(this.w*dpr);this.canvas.height=Math.round(this.h*dpr);}
    const c=this.ctx;c.setTransform(dpr,0,0,dpr,0,0);c.clearRect(0,0,this.w,this.h);
    if(this.w<160||this.h<180){this.scheduleFeaturedPulse(null);this.text('Expand chart to inspect',this.w/2,this.h/2,'#829daa',10,'center');return;}
    this.left=10;this.top=13;
    this.divider=Math.floor(Math.min(this.h*this.ratio,this.h-80));this.mainBottom=this.divider-15;this.quoteTop=this.divider+29;this.quoteBottom=this.h-28;
    if(!this.data||!this.data.candles?.length){this.scheduleFeaturedPulse(null);return;}
    const span=this.viewSpan(),from=this.end-span,scenarios=this.scenarioView();const bars=this.data.candles.filter(b=>b.time>=from-60&&b.time<=this.end+60);const emas=this.data.emas.filter(b=>b.time>=from-60&&b.time<=this.end+60);
    const autoRange=this.candleRange(bars,from,this.end);
    if(autoRange)this.lastObservedRange={...autoRange};
    this.range=this.manualY||autoRange||this.lastObservedRange;
    this.dockRange=this.range;
    const historyTicks=this.priceTicks(this.range);
    this.layoutPriceAxis(historyTicks);
    if(this.historyW<48){this.scheduleFeaturedPulse(null);this.text('Expand chart to inspect',this.w/2,this.h/2,'#829daa',10,'center');return;}
    if(!this.range){this.scheduleFeaturedPulse(null);this.text('Waiting for an observed price range',this.left+this.historyW/2,this.h/2,'#829daa',12,'center');return;}
    // Observed candles set the common scale, as in the original chart. Far
    // projected extrema may be off scale; they do not flatten source candles.
    for(const v of historyTicks.values){const y=this.y(v);this.line(this.left,y,this.plotRight,y,'#16314299');}
    const tick=span>10800?3600:span>5400?900:300;
    for(let t=Math.floor(from/tick)*tick;t<=this.end;t+=tick){const x=this.x(t);if(x<this.left||x>this.historyPlotRight)continue;const major=t%900===0;this.line(x,this.top,x,this.quoteBottom,major?'#3b687d99':'#17314188',1,major?[4,4]:[]);if(x<this.historyPlotRight-24)this.text(this.clock(t),x,this.h-9,major?'#a0bac9':'#658399',9,'center');}
    const forecastWindow=this.forecastWindow(),forecastTicks=this.forecastW>=250?[0,300,600,900]:[0,900];
    for(const offset of forecastTicks){const t=forecastWindow.start+offset,x=this.forecastX(t);this.line(x,this.top,x,this.quoteBottom,'#23435455',1,[2,5]);
      this.text(this.clock(t,true),x+(offset===0?5:offset===900?-5:0),this.h-9,'#90aab9',8,offset===0?'left':offset===900?'right':'center');}
    this.line(this.plotRight+1,0,this.plotRight+1,this.h,'#2d495b');this.line(0,this.divider,this.w,this.divider,'#2c4d61');
    this.text('NATIVE CONTRACT QUOTES',14,this.divider+18,'#85a3b5',9);this.text('0–1 · bid / ask · gaps remain gaps',this.historyPlotRight-8,this.divider+18,'#5d8196',8,'right');
    this.text('Future contract quotes unknown',this.dockLeft+8,this.divider+18,'#5d8196',8);
    for(const v of [0,.5,1]){const y=this.qy(v);this.line(this.left,y,this.historyPlotRight,y,'#152e3c');this.text(v.toFixed(2),this.w-5,y+3,'#7294a7',9,'right');}
    c.save();c.beginPath();c.rect(this.left,0,this.historyPlotRight-this.left,this.mainBottom+10);c.clip();
    if(this.selected){const a=this.x(this.selected.entry_ts),b=this.x(this.selected.exit_ts??this.data.market.time);c.fillStyle='#1d7a8d1c';c.fillRect(a,this.top,Math.max(2,b-a),this.mainBottom-this.top);this.line(a,this.top,a,this.mainBottom,'#35c2d77a',1,[2,3]);}
    this.drawTargetSegments(from,this.end,t=>this.x(t));
    const bodyWidth=Math.max(1,Math.min(20,this.historyW*60/span*.62));
    for(const b of bars){const x=this.x(b.time),up=b.close>=b.open,color=up?'#35cdb4':'#ec8575';const yOpen=this.y(b.open),yClose=this.y(b.close);this.line(x,this.y(b.high),x,this.y(b.low),color,1);const top=Math.min(yOpen,yClose),height=Math.max(1,Math.abs(yOpen-yClose));c.fillStyle=up?'#34c7b49e':'#e47b6bac';c.fillRect(x-bodyWidth/2,top,bodyWidth,height);if(b.quality==='sampled'){c.strokeStyle=color;c.lineWidth=1;c.setLineDash([2,2]);c.strokeRect(x-bodyWidth/2,top,bodyWidth,height);c.setLineDash([]);}else if((b.complete===false&&b.quality!=='sampled')){c.strokeStyle='#37cede';c.lineWidth=1.3;c.strokeRect(x-bodyWidth/2,top,bodyWidth,height);}else{c.fillStyle=color;c.fillRect(x-bodyWidth/2,top,bodyWidth,height);}}
    this.drawRoute();
    const gapGuides=this.emaGapGuides(this.data.candles,this.data.emas);
    this.drawEmaGapGuides(gapGuides,from,this.end);
    for(const [field,color]of[['e30','#e8ad51'],['e9','#37cede']]){c.save();c.beginPath();c.strokeStyle=color;c.lineWidth=this.focusVisual?(field==='e9'?3.1:2.8):(field==='e9'?1.8:1.5);if(this.focusVisual){c.shadowColor=color;c.shadowBlur=6;}let previous=null;for(const e of emas){if(!Number.isFinite(e[field])){previous=null;continue;}const x=this.x(e.time),y=this.y(e[field]);if(!Number.isFinite(y)){previous=null;continue;}if(previous===null||e.time-previous>90)c.moveTo(x,y);else c.lineTo(x,y);previous=e.time;}c.stroke();c.restore();}
    this.drawObservedEdge();
    const guide=this.physicalLegGuide(scenarios);this.currentGuide=guide;
    this.drawObservedLegGuide(guide);
    const market=this.data.market;if(Number.isFinite(market.btc)&&market.time>=from&&market.time<=this.end){this.line(this.left,this.y(market.btc),this.historyPlotRight,this.y(market.btc),market.fresh?'#30ceac77':'#758b9844',1,[2,4]);}
    this.drawTradeMarkers(bars,from);
    c.restore();
    if(bars.some(b=>b.quality==='sampled')){
      this.text('Dashed BTC candles = OBSERVED PARTIAL TICKS · not certified · not trading EMA',
        this.left+8,this.top+10,'#e4bf81',9);
    }
    if(gapGuides.some(g=>g.points.some(p=>p.time>=from&&p.time<=this.end))){
      this.text('Dashed EMA after source gap = display estimate, not trading EMA',
        this.left+8,this.top+23,'#b7a487',9);
    }
    if(!autoRange)this.text('No recorded candles in this window · Return to Live →',this.left+this.historyW/2,this.top+(this.mainBottom-this.top)/2,'#829daa',12,'center');
    this.drawLookingGlass(scenarios,guide);
    // One far-right axis and one current-price badge. No labels or boxes are
    // painted over the newest candle, its wick, or the live fan's origin.
    c.fillStyle='#08151e';c.fillRect(this.plotRight+2,this.top,this.priceAxisW-1,this.mainBottom-this.top);
    for(const v of historyTicks.values){const y=this.y(v);if(y<this.top+25)continue;
      this.text(this.price(v,historyTicks.step<1?2:0),this.w-5,y+3,'#85a9bb',10,'right');}
    this.text((this.data?.asset?.symbol||'BTC')+' $',this.w-5,this.top+10,'#a7bfd0',8,'right');
    if(Number.isFinite(market.btc)&&market.time>=from&&market.time<=this.end){
      const y=this.y(market.btc);
      if(y>=this.top&&y<=this.mainBottom)
        this.line(this.dockLeft,y,this.plotRight,y,market.fresh?'#30ceac77':'#758b9844',1,[2,4]);
      this.badge(this.price(market.btc),y,market.fresh?'#36cdb2':'#8dabb6');
    }
    if(Number.isFinite(market.target)&&(this.y(market.target)<this.top||this.y(market.target)>this.mainBottom))
      this.text((this.y(market.target)<this.top?'↑ ':'↓ ')+'TARGET OFF SCALE',this.plotRight-6,this.y(market.target)<this.top?this.top+10:this.mainBottom-4,'#d4b369',8,'right');
    const dockTarget=scenarios.targetContext;
    if(Number.isFinite(dockTarget?.target)&&dockTarget.target!==market.target&&this.dockRange&&
       (this.dockY(dockTarget.target)<this.top||this.dockY(dockTarget.target)>this.mainBottom))
      this.text((this.dockY(dockTarget.target)<this.top?'↑ ':'↓ ')+'TARGET OFF SCALE',this.plotRight-6,
        this.dockY(dockTarget.target)<this.top?this.top+10:this.mainBottom-4,'#d4b369',8,'right');
    // Contract lines stop at boundaries. Invalid quotes explicitly break paths.
    c.save();c.beginPath();c.rect(this.left,this.quoteTop,this.historyPlotRight-this.left,this.quoteBottom-this.quoteTop);c.clip();
    const quotes=this.data.quotes.filter(q=>q.time>=from-6&&q.time<=this.end);
    for(const [field,color]of[['yes_bid','#3dc9af'],['yes_ask','#7cdac5'],['no_bid','#e0a64c'],['no_ask','#f3ce8a']]){c.beginPath();c.strokeStyle=color;c.lineWidth=field.endsWith('bid')?1.25:.8;c.setLineDash(field.endsWith('ask')?[3,2]:[]);let prev=null;for(const q of quotes){const v=q[field];if(v===null||!Number.isFinite(v)){prev=null;continue;}const x=this.x(q.time),y=this.qy(v);if(prev&&q.ticker===prev.ticker&&q.time-prev.time<=6&&q.time>=prev.time){c.lineTo(x,this.qy(prev[field]));c.lineTo(x,y);}else c.moveTo(x,y);prev=q;}c.stroke();c.setLineDash([]);}
    c.restore();
    this.crosshair(bars,scenarios);
    if(typeof this.onViewport==='function')this.onViewport({follow:this.follow,span:this.span,visibleSpan:span,end:this.end});
    this.scheduleFeaturedPulse(scenarios);
  }
  crosshair(bars,scenarios=this.scenarioView()){
    if(!this.pointer||this.drag||this.pointer.x<this.left||this.pointer.x>this.plotRight||
       this.priceAxisAt(this.pointer.x)||
       (this.pointer.x>this.historyDataRight&&this.pointer.x<this.dockLeft)){
      this.tooltip.classList.add('hidden');return;}
    const p=this.pointer,inForecast=p.x>=this.dockLeft,t=inForecast?this.forecastTimeAt(p.x):this.historyTimeAt(p.x);
    this.line(p.x,this.top,p.x,this.quoteBottom,'#719aa175',1,[3,3]);
    if(p.y<this.mainBottom)this.line(inForecast?this.dockLeft:this.left,p.y,inForecast?this.plotRight:this.historyPlotRight,p.y,'#719aa14d',1,[3,3]);
    const marker=!inForecast&&this.tradeMarkerAt(p,12);
    if(marker){
      const {trade,event,annotation,source}=marker,value=trade[event==='entry'?'entry_ask':'exit_bid'];
      const lines=[`PAPER BOT · ${trade.side} ${event==='entry'?'ENTRY':'EXIT'}`,
        this.clock(trade[event+'_ts'],true)+' ET · '+trade.ticker,
        `Contract ${event==='entry'?'entry':'exit'} ${this.contractCents(value)}`];
      if(source)lines.push(`${this.data?.asset?.symbol||'BTC'} observation $${this.price(source.price)} · recorded with this event`);
      if(annotation)lines.push('Location annotation only · no recorded underlying-price coordinate');
      if(source?.source_conflict)lines.push('Recorded underlying source needs review');
      lines.push('Select this marker to inspect the bot trade');this.showTooltip(lines,p);return;
    }
    if(inForecast){
      const lines=[this.clock(t,true)+' ET · CONDITIONAL · LOOKING GLASS',
        '15-minute comparison clock · shared BTC price scale'];
      if(p.y>=this.mainBottom){lines.push('Future native contract quotes are unknown.');this.showTooltip(lines,p);return;}
      lines.push('Glass price at pointer $'+this.price(this.dockPriceAt(p.y)));
      if(Number.isFinite(scenarios.calendar_close_ts)&&t>scenarios.calendar_close_ts)lines.push('Beyond contract rollover · next contract target and quotes are unknown');
      if(scenarios.retained)lines.push(scenarios.status+' · issued '+this.clock(scenarios.glass.source_ts,true)+' ET · not a live forecast');
      const feature=scenarios.featured;
      if(feature){
        if(t<feature.source_ts)lines.push('Featured path begins '+this.clock(feature.source_ts,true)+' ET');
        else if(t>feature.horizon_ts)lines.push('Featured shape has ended · '+this.clock(feature.horizon_ts,true)+' ET');
        else lines.push((feature.fresh?'MAIN PATH':'RETAINED FEATURE')+' · '+feature.pattern.label+': '+
          this.price(feature.path.points.reduce((a,b)=>Math.abs(a.time-t)<Math.abs(b.time-t)?a:b).btc));
        if(!feature.fresh)lines.push(feature.reason);
      }
      const reference=scenarios.reference;
      if(reference){
        lines.push('CONDITIONAL REFERENCE · '+reference.label+' · not an engine pattern');
        if(t<reference.source_ts)lines.push('Reference begins '+this.clock(reference.source_ts,true)+' ET');
        else if(t>reference.horizon_ts)lines.push('Reference has ended · '+this.clock(reference.horizon_ts,true)+' ET');
        else lines.push('Reference spot '+this.price(reference.path.points.reduce((a,b)=>Math.abs(a.time-t)<Math.abs(b.time-t)?a:b).btc));
        lines.push(reference.status+' · issued '+this.clock(reference.source_ts,true)+' ET');
        if(!reference.history_verified_at_issue)lines.push('History unverified · '+reference.physical_status_at_issue);
      }
      for(const [family,label]of [['CONTINUATION','Continuation'],['ROTATION_STALL','Rotation / stall'],['REVERSAL','Return / reversal']]){
        const values=scenarios.paths.filter(path=>path.family===family&&t>=path.points[0].time&&t<=path.points.at(-1).time)
          .map(path=>path.points.reduce((a,b)=>Math.abs(a.time-t)<Math.abs(b.time-t)?a:b).btc);
        if(values.length)lines.push(label+': '+this.price(Math.min(...values))+(Math.max(...values)>Math.min(...values)?' – '+this.price(Math.max(...values)):''));
      }
      if(!scenarios.paths.length&&!feature&&!reference)lines.push(scenarios.reason||'No issued paths available');
      lines.push('Nearest issued sample · no win probabilities');this.showTooltip(lines,p);return;
    }
    const b=bars.reduce((a,b)=>!a||Math.abs(b.time-t)<Math.abs(a.time-t)?b:a,null);if(!b||Math.abs(b.time-t)>45){this.tooltip.classList.add('hidden');return;}
    const ema=this.data.emas.find(e=>e.time===b.time);const lines=[this.clock(b.time)+' ET · 1 minute',`O ${this.price(b.open)}   H ${this.price(b.high)}`,`L ${this.price(b.low)}   C ${this.price(b.close)}`,b.quality==='sampled'?'SAMPLED OHLC · extremes may be missing':b.complete===false?'DEVELOPING TRADE BAR · not complete':'COMPLETED SOURCE BAR · '+(b.source||b.quality)];
    if(Number.isFinite(b.first_observed_in_scan))lines.push('Earliest scanned observation '+this.clock(b.first_observed_in_scan,true)+' ET');
    else if(Number.isFinite(b.known_at))lines.push('Snapshot observation '+this.clock(b.known_at,true)+' ET');
    if(ema)lines.push(`NAEVYR ${this.price(ema.e9)}  THAERYON ${this.price(ema.e30)}`);
    const pivot=this.route.pivots.find(point=>point.time===b.time);
    if(pivot)lines.push(`Swing ${pivot.kind.toLowerCase()} confirmed ${this.clock(pivot.confirmedAt)} ET · display only`);
    this.showTooltip(lines,p);
  }
  contractCents(value){return Number.isFinite(value)&&value>=0&&value<=1?
    (value*100).toLocaleString('en-US',{maximumFractionDigits:4})+'¢':'—';}
  tradeMarkerAt(point,radius=16){
    const label=this.markers.find(marker=>marker.labelBounds&&point.x>=marker.labelBounds.left&&
      point.x<=marker.labelBounds.right&&point.y>=marker.labelBounds.top&&point.y<=marker.labelBounds.bottom);
    if(label)return label;
    let nearest=null,distance=radius;
    for(const marker of this.markers){const delta=Math.hypot(marker.x-point.x,marker.y-point.y);
      if(delta<distance){nearest=marker;distance=delta;}}
    return nearest;
  }
  drawTradeMarkers(bars,from){
    const c=this.ctx;this.markers=[];
    // Native open positions normally also appear in trades. Include a position
    // only when that real entry is absent; never synthesize a current setup.
    const identity=trade=>[trade.ticker,trade.position_id??trade.trade_id??trade.key,trade.entry_ts,trade.side].join('|'),
      trades=[...(this.data.trades||[])],seen=new Set(trades.map(identity));
    for(const position of this.data.positions||[]){const key=identity(position);
      if(!seen.has(key)){seen.add(key);trades.push(position);}}
    const scale=Math.max(.95,Math.min(1.5,this.fontScale));
    for(const trade of trades){for(const event of ['entry','exit']){
      const time=trade[event+'_ts'];if(!Number.isFinite(time)||time<from||time>this.end)continue;
      if(!['YES','NO'].includes(trade.side))continue;
      const source=this.eventBtcView(trade,event);
      const bar=bars.find(bar=>bar.time===Math.floor(time/60)*60);
      if(!source&&!bar)continue;
      const x=this.x(time),below=trade.side==='YES',annotation=!source,
        y=source?this.y(source.price):this.y(below?bar.low:bar.high)+(below?14:-14),
        color=event==='exit'?'#c0d2df':trade.side==='YES'?'#51dfbc':'#f1c272',
        selected=Boolean(this.selected&&identity(this.selected)===identity(trade)),size=(event==='exit'?4:5)*scale;
      if(!Number.isFinite(y)||x<this.left||x>this.historyPlotRight||y<this.top||y>this.mainBottom)continue;
      c.save();c.beginPath();c.fillStyle=color;c.strokeStyle=color;c.lineWidth=1.5*scale;
      c.shadowColor='#031019';c.shadowBlur=selected?8:5;
      if(event==='exit'){
        // Hollow diamond exits stay visually distinct from filled entry arrows.
        c.moveTo(x,y-size);c.lineTo(x+size,y);c.lineTo(x,y+size);c.lineTo(x-size,y);c.closePath();
        c.fillStyle='#07151e';c.fill();c.stroke();
      }
      else if(source){
        // The triangle's tip is the exact recorded observation coordinate.
        // Its label is offset; neither later candles nor current BTC move it.
        c.moveTo(x,y);c.lineTo(x-size,y+(below?1:-1)*size*1.6);c.lineTo(x+size,y+(below?1:-1)*size*1.6);c.closePath();
        c.fill();c.strokeStyle='#07151e';c.lineWidth=1.2;c.stroke();
      }else{
        c.moveTo(x,y+(below?-size:size));c.lineTo(x-size,y+(below?size*.6:-size*.6));c.lineTo(x+size,y+(below?size*.6:-size*.6));c.closePath();c.stroke();
      }
      c.restore();
      this.markers.push({x,y,trade,event,annotation,source,selected,size,below,color,btc_observation:source?.price??null,
        entry_btc:event==='entry'?(source?.price??null):null,
        exit_btc:event==='exit'?(source?.price??null):null});
    }}
    const occupied=[],priority=marker=>marker.selected?0:marker.event==='entry'?(marker.trade.closed===false?1:2):3,
      queue=[...this.markers].sort((a,b)=>priority(a)-priority(b)||b.trade[b.event+'_ts']-a.trade[a.event+'_ts']),
      labelLimit=Math.max(6,Math.floor(this.historyW/52)*3);
    for(const marker of queue.slice(0,labelLimit)){
      const {x,y,trade,event,annotation,source,selected,size,below,color}=marker,
        value=trade[event==='entry'?'entry_ask':'exit_bid'],
        label=(event==='entry'?trade.side+' IN ':'OUT ')+this.contractCents(value)+(annotation||source?.source_conflict?' *':''),
        fontSize=Math.max(10.5,Math.min(17,(selected?11.5:10.5)*this.fontScale)),
        height=Math.ceil(fontSize+10);
      c.save();c.font=`600 ${fontSize}px "Segoe UI",sans-serif`;
      const width=Math.ceil(c.measureText(label).width+14);
      if(width>this.historyPlotRight-this.left-8){c.restore();continue;}
      const clampX=value=>Math.max(this.left+4,Math.min(this.historyPlotRight-width-4,value)),
        xs=[clampX(x+size+5),clampX(x-width-size-5),clampX(x-width/2)],candidates=[];
      for(let row=0;row<3;row++)for(const down of [below,!below])for(const left of xs){
        const top=down?y+size*1.6+5+row*(height+5):y-size-5-height-row*(height+5);
        candidates.push({left,right:left+width,top,bottom:top+height});
      }
      const box=candidates.find(box=>box.top>=this.top+34&&box.bottom<=this.mainBottom-4&&
        !occupied.some(other=>box.left<other.right+4&&box.right>other.left-4&&box.top<other.bottom+4&&box.bottom>other.top-4)&&
        !this.markers.some(other=>other!==marker&&other.x+other.size+3>box.left&&other.x-other.size-3<box.right&&
          other.y+other.size*1.6+3>box.top&&other.y-other.size*1.6-3<box.bottom));
      if(!box){c.restore();continue;}
      const connectorX=Math.max(box.left+4,Math.min(box.right-4,x)),connectorY=box.top>y?box.top:box.bottom;
      this.line(x,y+(box.top>y?size*1.6:-size),connectorX,connectorY,color+'80',1);
      c.fillStyle='#07151ef2';c.fillRect(box.left,box.top,width,height);
      c.strokeStyle=color+(selected?'dd':'80');c.lineWidth=selected?1.5:1;c.strokeRect(box.left+.5,box.top+.5,width-1,height-1);
      c.fillStyle=color;c.textAlign='left';c.fillText(label,box.left+7,box.top+5+fontSize*.8);
      c.restore();marker.labelBounds=box;occupied.push(box);
    }
  }
  showTooltip(lines,p){this.tooltip.textContent=lines.join('\n');this.tooltip.classList.remove('hidden');this.tooltip.style.left=Math.max(6,Math.min(this.w-290,p.x+15))+'px';this.tooltip.style.top=Math.max(5,Math.min(this.h-170,p.y+15))+'px';}
}
window.NautilusChart=NautilusChart;
