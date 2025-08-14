import os, logging, requests
def fetch_clarity_json():
    t=os.getenv("CLARITY_API_TOKEN")
    if not t: logging.info({"event":"clarity_skip"}); return None
    params={"numOfDays":os.getenv("CLARITY_NUM_DAYS","1")}
    for k in ("CLARITY_DIM1","CLARITY_DIM2","CLARITY_DIM3"):
        v=os.getenv(k,"").strip()
        if v: params[f"dimension{k[-1]}"]=v
    h={"Authorization":f"Bearer {t}","Content-type":"application/json"}
    try:
        r=requests.get("https://www.clarity.ms/export-data/api/v1/project-live-insights", params=params, headers=h, timeout=25)
        r.raise_for_status(); return r.json()
    except Exception: logging.exception("clarity_fetch_failed"); return None
