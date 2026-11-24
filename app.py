from __future__ import annotations
import csv, io, os, sqlite3, statistics, random
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Header, UploadFile, File, Depends
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('SMARTGRID_DB', BASE / 'smartgrid.db'))
API_KEY = os.getenv('SMARTGRID_INGEST_KEY', '')
app = FastAPI(title='Gridline | Smart Energy Platform', version='1.0.0', description='Evidence-based energy monitoring and analysis platform')
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS','http://localhost:8000').split(','), allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['Content-Type','X-API-Key'])
app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')

class Reading(BaseModel):
    device_id: str = Field(min_length=1, max_length=80)
    timestamp: datetime
    voltage_v: float = Field(ge=0, le=1000)
    current_a: float = Field(ge=0, le=5000)
    active_power_w: float = Field(ge=0, le=2_000_000)
    energy_kwh: Optional[float] = Field(default=None, ge=0)
    power_factor: Optional[float] = Field(default=None, ge=0, le=1)
    frequency_hz: Optional[float] = Field(default=None, ge=0, le=100)

class Tariff(BaseModel):
    rate_per_kwh: float = Field(gt=0, le=100000)
    currency: str = Field(default='INR', min_length=3, max_length=3)


def db():
    con=sqlite3.connect(DB_PATH)
    con.row_factory=sqlite3.Row
    return con

def init_db():
    with db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS readings(id INTEGER PRIMARY KEY AUTOINCREMENT, device_id TEXT NOT NULL, timestamp TEXT NOT NULL, voltage_v REAL NOT NULL, current_a REAL NOT NULL, active_power_w REAL NOT NULL, energy_kwh REAL, power_factor REAL, frequency_hz REAL, source TEXT NOT NULL DEFAULT 'device', UNIQUE(device_id,timestamp))''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL)''')
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('rate_per_kwh','8.0')")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('currency','INR')")
        c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('fixed_charge','100')")
init_db()

def require_key(x_api_key: Optional[str] = Header(default=None)):
    if not API_KEY:
        raise HTTPException(503, 'Ingestion is disabled: configure SMARTGRID_INGEST_KEY on the server.')
    if x_api_key != API_KEY:
        raise HTTPException(401, 'Invalid API key')

@app.get('/', response_class=HTMLResponse)
def home():
    return (BASE/'templates'/'index.html').read_text(encoding="utf-8")

@app.get('/api/status')
def status():
    with db() as c:
        n=c.execute('SELECT COUNT(*) n FROM readings').fetchone()['n']
        last=c.execute('SELECT timestamp,device_id,source FROM readings ORDER BY timestamp DESC LIMIT 1').fetchone()
        devices=c.execute('SELECT COUNT(DISTINCT device_id) n FROM readings').fetchone()['n']
    return {'status':'operational','data_mode':('simulation' if last and last['source']=='simulation' else 'measured_or_imported') if n else 'no_data','readings':n,'devices':devices,'last_reading':dict(last) if last else None,'ingestion_enabled':bool(API_KEY)}

@app.post('/api/readings', dependencies=[Depends(require_key)])
def ingest(r: Reading):
    ts=r.timestamp.astimezone(timezone.utc).isoformat()
    with db() as c:
        try:
            c.execute('INSERT INTO readings(device_id,timestamp,voltage_v,current_a,active_power_w,energy_kwh,power_factor,frequency_hz,source) VALUES(?,?,?,?,?,?,?,?,?)',(r.device_id,ts,r.voltage_v,r.current_a,r.active_power_w,r.energy_kwh,r.power_factor,r.frequency_hz,'device'))
        except sqlite3.IntegrityError: raise HTTPException(409,'A reading for this device and timestamp already exists')
    return {'accepted':True,'timestamp_utc':ts,'source':'device'}

@app.post('/api/import-csv')
def import_csv(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.csv'): raise HTTPException(400,'Upload a CSV file')
    raw=file.file.read()
    if len(raw)>5_000_000: raise HTTPException(413,'CSV exceeds 5 MB limit')
    try:
        rows=list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
        required={'device_id','timestamp','voltage_v','current_a','active_power_w'}
        if not rows or not required.issubset(set(rows[0])): raise ValueError('Required columns: '+', '.join(sorted(required)))
        inserted=0
        with db() as c:
            for row in rows:
                r=Reading(**{k:(row.get(k) or None) for k in ['device_id','timestamp','voltage_v','current_a','active_power_w','energy_kwh','power_factor','frequency_hz']})
                try:
                    c.execute('INSERT INTO readings(device_id,timestamp,voltage_v,current_a,active_power_w,energy_kwh,power_factor,frequency_hz,source) VALUES(?,?,?,?,?,?,?,?,?)',(r.device_id,r.timestamp.astimezone(timezone.utc).isoformat(),r.voltage_v,r.current_a,r.active_power_w,r.energy_kwh,r.power_factor,r.frequency_hz,'import'))
                    inserted+=1
                except sqlite3.IntegrityError: pass
        return {'imported':inserted,'source':'import','rows_seen':len(rows)}
    except Exception as e:
        if isinstance(e,HTTPException): raise
        raise HTTPException(400,f'CSV parsing failed: {e}')

@app.get('/api/readings')
def readings(limit: int=200):
    limit=max(1,min(limit,2000))
    with db() as c: rows=c.execute('SELECT * FROM readings ORDER BY timestamp DESC LIMIT ?', (limit,)).fetchall()
    return [dict(x) for x in rows][::-1]

@app.post('/api/simulate')
def simulate(profile: str = '2bhk', days: int = 7):
    """Create explicitly labelled synthetic household telemetry for demos and testing."""
    profiles = {
        '1bhk': {'base': 95, 'ac': 1200, 'geyser': 1800, 'extra': 0.75},
        '2bhk': {'base': 145, 'ac': 1500, 'geyser': 2000, 'extra': 1.0},
        '3bhk': {'base': 210, 'ac': 1800, 'geyser': 2200, 'extra': 1.35},
        '3bhk_plus': {'base': 290, 'ac': 2100, 'geyser': 2500, 'extra': 1.7},
    }
    if profile not in profiles: raise HTTPException(400, 'Choose 1bhk, 2bhk, 3bhk or 3bhk_plus')
    days = max(1, min(int(days), 30)); cfg=profiles[profile]; rng=random.Random(4217 + days + len(profile))
    now=datetime.now().astimezone().replace(minute=0,second=0,microsecond=0)
    samples=[]; cumulative=0.0
    for i in range(days*24):
        ts=now-timedelta(hours=days*24-1-i); h=ts.hour; weekday=ts.weekday()
        # Representative Indian home schedule: morning cooking/hot water, daytime occupancy,
        # evening lighting/cooking/entertainment, and overnight base load.
        load=cfg['base']
        if 6 <= h <= 9: load += 260*cfg['extra']
        if 19 <= h <= 23: load += 390*cfg['extra']
        if 0 <= h <= 5: load *= .68
        if 10 <= h <= 17: load *= .78 if weekday < 5 else .95
        # Refrigerator cycles, fans, lights and electronics.
        load += (90 if h in range(6,10) or h in range(18,24) else 35)*cfg['extra']
        if h in (6,7,8,19,20,21): load += cfg['geyser'] * rng.choice([0,0,0,0.35,0.65])
        if h in (13,14,15,16,21,22): load += cfg['ac'] * rng.choice([0,0.25,0.45,0.7,1.0])
        if h in (7,8,20,21): load += 450*cfg['extra'] # cooking and kitchen appliances
        power=max(45,load*rng.uniform(.90,1.10)); voltage=rng.uniform(224,238); pf=rng.uniform(.88,.97)
        current=power/(voltage*pf); cumulative += power/1000
        samples.append((f'DEMO-{profile.upper()}',ts.isoformat(),round(voltage,2),round(current,3),round(power,2),round(cumulative,5),round(pf,3),50.0,'simulation'))
    with db() as c:
        c.execute("DELETE FROM readings WHERE source='simulation'")
        c.executemany('INSERT INTO readings(device_id,timestamp,voltage_v,current_a,active_power_w,energy_kwh,power_factor,frequency_hz,source) VALUES(?,?,?,?,?,?,?,?,?)',samples)
    return {'generated':len(samples),'source':'simulation','profile':profile,'days':days,'device_id':f'DEMO-{profile.upper()}','notice':'Synthetic demonstration data. Not measured from a physical meter.'}

@app.get('/api/analytics')
def analytics():
    with db() as c:
        rows=[dict(x) for x in c.execute('SELECT * FROM readings ORDER BY timestamp ASC').fetchall()]
        rate=float(c.execute("SELECT value FROM settings WHERE key='rate_per_kwh'").fetchone()[0])
        currency=c.execute("SELECT value FROM settings WHERE key='currency'").fetchone()[0]
    if not rows: return {'has_data':False,'message':'No meter readings yet. Connect a device or import measured readings.','source':'none'}
    # Prefer cumulative energy register when present; otherwise integrate power over observed intervals.
    energy_values=[r['energy_kwh'] for r in rows]
    total_kwh=None; energy_method=None
    valid=[(i,v) for i,v in enumerate(energy_values) if v is not None]
    if len(valid)>=2 and valid[-1][1]>=valid[0][1]:
        total_kwh=round(valid[-1][1]-valid[0][1],4); energy_method='cumulative_meter_register'
    elif len(rows)>=2:
        total=0.0
        for a,b in zip(rows,rows[1:]):
            try: hours=(datetime.fromisoformat(b['timestamp'])-datetime.fromisoformat(a['timestamp'])).total_seconds()/3600
            except: continue
            if 0<hours<=6: total += ((a['active_power_w']+b['active_power_w'])/2/1000)*hours
        total_kwh=round(total,4); energy_method='trapezoidal_power_integration'
    else: energy_method='insufficient_intervals'
    powers=[r['active_power_w'] for r in rows]
    # Robust outlier flagging: median absolute deviation; suppress when sample is too small or MAD=0.
    med=statistics.median(powers); deviations=[abs(x-med) for x in powers]; mad=statistics.median(deviations)
    anomalies=[]
    if len(powers)>=8 and mad>0:
        for r in rows:
            score=0.6745*(r['active_power_w']-med)/mad
            if abs(score)>3.5: anomalies.append({'timestamp':r['timestamp'],'device_id':r['device_id'],'power_w':r['active_power_w'],'robust_score':round(score,2),'method':'modified_z_score_MAD'})
    profile={}
    for r in rows:
        h=datetime.fromisoformat(r['timestamp']).astimezone(__import__('zoneinfo').ZoneInfo('Asia/Kolkata')).strftime('%H:00 IST')
        profile.setdefault(h,[]).append(r['active_power_w'])
    hourly=[{'hour':h,'avg_power_w':round(statistics.mean(v),2),'samples':len(v)} for h,v in sorted(profile.items())]
    latest=rows[-1]
    return {'has_data':True,'source':('simulation' if all(r['source']=='simulation' for r in rows) else 'mixed' if any(r['source']=='simulation' for r in rows) else 'measured_or_imported'),'reading_count':len(rows),'device_count':len(set(r['device_id'] for r in rows)),'latest':latest,'average_power_w':round(statistics.mean(powers),2),'peak_power_w':round(max(powers),2),'min_power_w':round(min(powers),2),'total_energy_kwh':total_kwh,'energy_method':energy_method,'estimated_cost':round(total_kwh*rate,2) if total_kwh is not None else None,'tariff':{'rate_per_kwh':rate,'currency':currency},'anomaly_count':len(anomalies),'anomalies':anomalies[-30:],'hourly_profile':hourly,'source_breakdown':{s:sum(1 for r in rows if r['source']==s) for s in set(r['source'] for r in rows)}}

@app.post('/api/tariff')
def set_tariff(t: Tariff):
    with db() as c:
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('rate_per_kwh',?)",(str(t.rate_per_kwh),))
        c.execute("INSERT OR REPLACE INTO settings(key,value) VALUES('currency',?)",(t.currency.upper(),))
    return {'saved':True,'tariff':t.model_dump()}

@app.get('/api/export.csv')
def export_csv():
    with db() as c: rows=c.execute('SELECT device_id,timestamp,voltage_v,current_a,active_power_w,energy_kwh,power_factor,frequency_hz,source FROM readings ORDER BY timestamp').fetchall()
    out=io.StringIO(); w=csv.writer(out); w.writerow(['device_id','timestamp','voltage_v','current_a','active_power_w','energy_kwh','power_factor','frequency_hz','source']); w.writerows([tuple(r) for r in rows])
    return JSONResponse({'csv':out.getvalue(),'rows':len(rows)})
