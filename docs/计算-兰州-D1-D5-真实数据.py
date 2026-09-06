# -*- coding: utf-8 -*-
"""
兰州 D1~D5 真实数据计算脚本（可复现）
======================================
- 数据：NASA POWER（MERRA2/SYN1DEG）2019-2023 五年平均，坐标 36.05N/103.83E，
  参数 ALLSKY_SFC_SW_DWN / ALLSKY_SFC_SW_DIFF / T2M / T2M_MIN / T2M_MAX。
- 极端气温：兰州历史最高 39.8℃(2010-07-29)、市区历史最低 -21.7℃(1964-01-27)。
- 负荷：兰州专属口径，设备功率经官网核验（2026-09-06）；冬季采暖月 7.61 kWh/d，学号末位 4/5 → 区间 7.5~8.0。
- 方法：指导书 §2.2/§2.3/§2.4/§3.1/§3.2/§3.3/§5.2~5.4/§6.1~6.4。
运行：python3 计算-兰州-D1-D5-真实数据.py   （需联网抓取；已存在本地 JSON 则直接复用）
"""
import json, math, os, requests

LAT, LON = 36.05, 103.83
OUT_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "数据-兰州-NASA-POWER-2019-2023.json")
PARAMS = "ALLSKY_SFC_SW_DWN,ALLSKY_SFC_SW_DIFF,T2M,T2M_MIN,T2M_MAX"

def fetch():
    url = "https://power.larc.nasa.gov/api/temporal/monthly/point"
    r = requests.get(url, params={"parameters": PARAMS, "community": "RE",
                                  "longitude": LON, "latitude": LAT,
                                  "start": "2019", "end": "2023", "format": "JSON"}, timeout=60)
    r.raise_for_status()
    return r.json()

data = None
if os.path.exists(OUT_JSON):
    data = json.load(open(OUT_JSON, encoding="utf-8"))
else:
    raw = fetch()
    P = raw["properties"]["parameter"]
    data = {"lat": LAT, "lon": LON, "source": "NASA POWER MERRA2/SYN1DEG",
            "period": "2019-2023", "elevation_m": raw["geometry"]["coordinates"][2]}
    for p in PARAMS.split(","):
        data[p] = {}
        for m in range(1, 13):
            vals = [P[p][f"{y}{m:02d}"] for y in range(2019, 2024)]
            vals = [v for v in vals if v != -999.0]
            data[p][str(m)] = round(sum(vals)/len(vals), 3) if vals else None
    json.dump(data, open(OUT_JSON, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

G  = data["ALLSKY_SFC_SW_DWN"]; D = data["ALLSKY_SFC_SW_DIFF"]; T = data["T2M"]
days = [31,28,31,30,31,30,31,31,30,31,30,31]; doy = [15,46,74,105,135,162,198,229,259,289,320,349]
phi = math.radians(36.05); rho = 0.2

def decl(day): return math.radians(23.45*math.sin(math.radians(360*(284+day)/365.0)))
def liu(m, beta):
    dlt = decl(doy[m-1]); be = math.radians(beta); pe = phi - be
    ws = math.acos(max(-1, min(1, -math.tan(phi)*math.tan(dlt))))
    nh = ws*math.sin(phi)*math.sin(dlt) + math.cos(phi)*math.cos(dlt)*math.sin(ws)
    a = -math.tan(pe)*math.tan(dlt)
    wsp = min(ws, math.acos(max(-1, min(1, a)))) if -1 <= a <= 1 else (ws if a < -1 else 0.0)
    nt = wsp*math.sin(pe)*math.sin(dlt) + math.cos(pe)*math.cos(dlt)*math.sin(wsp)
    Rb = nt/nh if nh > 0 else 0.0
    g, d = G[str(m)], D[str(m)]
    return (g-d)*Rb + d*(1+math.cos(be))/2 + g*rho*(1-math.cos(be))/2, Rb

BETA = 35
Ht = [liu(m, BETA)[0] for m in range(1, 13)]
EAC = [7.61]*3 + [4.61, 3.41, 4.42, 4.42, 4.42, 3.41, 4.61, 7.61, 7.61]
Rh  = [round(EAC[i]/G[str(i+1)], 2) for i in range(12)]
Rt  = [round(EAC[i]/Ht[i], 2) for i in range(12)]
annual = sum(H*dd for H, dd in zip(Ht, days))
print("== D3 ==")
print("12月峰值日照 水平 %.2f h/d; 倾斜%d° %.2f h/d; 倾斜全年 %.0f kWh/m2.yr" % (G["12"], BETA, Ht[11], annual))
print("R(水平):", Rh, "-> 最不利月", Rh.index(max(Rh))+1)
# 温度
def Tcell(ta): return ta + (45-20)/800.0*1000.0
print("Tcell 极端(39.8) = %.1f; 7月常态(%.1f) = %.1f" % (Tcell(39.8), T["7"], Tcell(T["7"])))
# 蓄电池
Ebat = 7.61*2*1.10/(0.90*0.95*0.93*1.00); Cbat = 1000*Ebat/51.2
NPe = math.ceil(Ebat/5.12); Eact = NPe*5.12
Idis = 5000/(45*0.93); Idis_sur = 4800/(45*0.93)
print("== D5 ==  Ebat,min=%.2f  Cbat=%.1fAh  N_P,E=%d  实际=%.2f (%.2fx)" % (Ebat, Cbat, NPe, Eact, Eact/Ebat))
print("Idis=%.1f A  Idis,sur=%.1f A" % (Idis, Idis_sur))
# 光伏
PPVmin = 7.61*1.10/(Ht[11]*0.782)
Voc_c = 52.22*(1+(-0.0023)*(-21.7-25)); Vmp_h = 44.12*(1+(-0.0028)*(Tcell(39.8)-25)); Vmp_c = 44.12*(1+(-0.0028)*(-46.7))
NSmin = math.ceil(120/Vmp_h); NSmax = math.floor(500/Voc_c)
print("== 附录A ==  P_PV,min=%.2f kWp  Voc,cold=%.2f V  Vmp,hot=%.2f V  Vmp,cold=%.2f V  N_S∈[%d,%d]"
      % (PPVmin, Voc_c, Vmp_h, Vmp_c, NSmin, NSmax))
for NS in range(NSmin, NSmax+1):
    ppv = NS*0.6; ratio = ppv*Ht[11]*0.782/7.61
    print("  N_S=%d -> %.2f kWp, 12月供能比=%.2f, 组串Voc,cold=%.0fV" % (NS, ppv, ratio, NS*Voc_c))
Ichg = min(4*600*0.96/54.4, 100)
print("I_chg(4串2.4kWp) = %.1f A" % Ichg)
print("保存原始数据:", OUT_JSON)
