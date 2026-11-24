const $=id=>document.getElementById(id);let analyticsData=null;
function fmt(n,d=2){return n==null?'—':Number(n).toLocaleString('en-IN',{maximumFractionDigits:d,minimumFractionDigits:d})}
function toast(s){const t=$('toast');t.textContent=s;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2800)}
async function api(url, opts = {}) {
    let response;

    try {
        response = await fetch(url, {
            ...opts,
            headers: {
                "Content-Type": "application/json",
                ...(opts.headers || {})
            }
        });
    } catch (error) {
        throw new Error(
            "Cannot connect to Gridline API. Check that the backend is running."
        );
    }

    const text = await response.text();

    let data;

    try {
        data = text ? JSON.parse(text) : {};
    } catch {
        throw new Error(
            `Server returned invalid JSON. HTTP ${response.status}`
        );
    }

    if (!response.ok) {
        throw new Error(
            data.detail || `Request failed: HTTP ${response.status}`
        );
    }

    return data;
}
async function refresh(){try{const [s,a,rs]=await Promise.all([api('/api/status'),api('/api/analytics'),api('/api/readings?limit=100')]);analyticsData=a;$('connection').innerHTML=`<i style="background:${s.readings?'#39845a':'#b5a36e'}"></i>${s.data_mode==='simulation'?'SIMULATION DATA':s.readings?'IMPORTED / MEASURED DATA':'READY FOR DEMO'}`;$('sideStatus').textContent=s.readings?'Database reachable':'Ready to generate demo';$('notice').style.display=(a.has_data && s.data_mode!=='simulation')?'none':'flex';$('dataModeLabel').textContent=s.data_mode==='simulation'?'SIMULATED DATA':s.readings?'IMPORTED / MEASURED DATA':'NO DATA';if(a.has_data){$('latestPower').innerHTML=`${fmt(a.latest.active_power_w/1000)} <small>kW</small>`;$('latestTime').textContent=new Date(a.latest.timestamp).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST';$('energy').innerHTML=`${a.total_energy_kwh==null?'—':fmt(a.total_energy_kwh)} <small>kWh</small>`;$('energyMethod').textContent=a.energy_method.replaceAll('_',' ');$('peak').innerHTML=`${fmt(a.peak_power_w/1000)} <small>kW</small>`;$('anomalies').textContent=a.anomaly_count;$('anomalyText').textContent=a.anomaly_count?`${a.anomaly_count} unusual sample(s) flagged`:'No outliers flagged';$('records').textContent=a.reading_count;$('deviceCount').textContent=a.device_count;$('average').textContent=fmt(a.average_power_w)+' W';$('origin').textContent=Object.keys(a.source_breakdown).join(', ').toUpperCase();$('sampleCount').textContent=`${a.reading_count} samples`;$('cost').textContent=a.estimated_cost==null?'—':`₹${fmt(a.estimated_cost)}`;$('costNote').textContent=a.estimated_cost==null?'Insufficient readings to calculate energy':'Flat tariff × measured energy';$('rate').value=a.tariff.rate_per_kwh;drawChart(a.hourly_profile)}else{drawChart([])}renderRows(rs)}catch(e){$('connection').innerHTML='<i></i> API UNAVAILABLE';$('sideStatus').textContent='API unavailable';toast(e.message)}}
function renderRows(rows){$('readingRows').innerHTML=rows.length?rows.slice(-12).reverse().map(r=>`<tr><td>${new Date(r.timestamp).toLocaleString('en-IN',{timeZone:'Asia/Kolkata'})+' IST'}</td><td>${esc(r.device_id)}</td><td>${fmt(r.voltage_v)} V</td><td>${fmt(r.current_a)} A</td><td>${fmt(r.active_power_w)} W</td><td>${r.power_factor==null?'—':fmt(r.power_factor,3)}</td><td>${esc(r.source.toUpperCase())}</td></tr>`).join(''):'<tr><td colspan="7" class="no-rows">No readings yet. Generate a simulated household data set above.</td></tr>'}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function drawChart(data){const c=$('chart'),ctx=c.getContext('2d'),wrap=c.parentElement,empty=$('chartEmpty');const w=wrap.clientWidth,h=wrap.clientHeight,dpr=window.devicePixelRatio||1;c.width=w*dpr;c.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);if(!data||!data.length){empty.style.display='flex';return}empty.style.display='none';const vals=data.map(x=>Number(x.avg_power_w)||0),max=Math.max(...vals,1)*1.15,pad={l:42,r:12,t:12,b:25},cw=w-pad.l-pad.r,ch=h-pad.t-pad.b;ctx.font='9px DM Mono';ctx.fillStyle='#89938b';ctx.strokeStyle='#edf0ed';ctx.lineWidth=1;for(let i=0;i<4;i++){let y=pad.t+ch*i/3;ctx.beginPath();ctx.moveTo(pad.l,y);ctx.lineTo(w-pad.r,y);ctx.stroke();ctx.fillText(Math.round(max*(1-i/3)).toLocaleString('en-IN'),2,y+3)}const pts=vals.map((v,i)=>({x:pad.l+(data.length===1?cw/2:cw*i/(data.length-1)),y:pad.t+ch*(1-v/max)}));ctx.beginPath();pts.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.strokeStyle='#287a50';ctx.lineWidth=2;ctx.lineJoin='round';ctx.lineCap='round';ctx.stroke();pts.forEach(p=>{ctx.beginPath();ctx.arc(p.x,p.y,2.6,0,Math.PI*2);ctx.fillStyle='#287a50';ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.stroke()});ctx.fillStyle='#89938b';ctx.textAlign='left';ctx.fillText(data[0].hour,pad.l,h-5);ctx.textAlign='right';ctx.fillText(data.at(-1).hour,w-pad.r,h-5);ctx.textAlign='left'}
async function saveTariff(){try{await api('/api/tariff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({rate_per_kwh:Number($('rate').value),currency:'INR'})});toast('Tariff saved');refresh()}catch(e){toast(e.message)}}
$('csvFile').addEventListener('change',async e=>{const f=e.target.files[0];if(!f)return;const fd=new FormData();fd.append('file',f);try{const r=await api('/api/import-csv',{method:'POST',body:fd});toast(`Imported ${r.imported} measured rows`);refresh()}catch(err){toast(err.message)}e.target.value=''});
window.addEventListener('resize',()=>{if(analyticsData?.has_data)drawChart(analyticsData.hourly_profile)});refresh();setInterval(refresh,30000);

async function generateDemo(){const btn=$('generateBtn');btn.disabled=true;btn.textContent='Generating…';try{const profile=$('homeProfile').value,days=$('simDays').value;const r=await api(`/api/simulate?profile=${encodeURIComponent(profile)}&days=${encodeURIComponent(days)}`,{method:'POST'});toast(`Generated ${r.generated} simulated readings`);await refresh()}catch(e){toast(e.message)}finally{btn.disabled=false;btn.textContent='Generate demo readings'}}
