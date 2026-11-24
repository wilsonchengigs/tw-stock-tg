import importlib.util,sys,os
os.chdir(r'C:\Users\wilsoncheng\Desktop\tw-stock-tg\backtest'); sys.path.insert(0,'.')
spec=importlib.util.spec_from_file_location('r9','research_09_多市場分散.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
N,WE,ME=r.N,r.WE,r.ME
def sig(leg,n,monthly):
    m=leg.sma(n); st=False; out=[]
    for i in range(N):
        k=leg.idx[i]
        if k>=n and ((ME[i] if monthly else WE[i])):
            st=leg.up[k]>m[k]
        out.append(st)
    return out
L=[]
def p(s): L.append(s); print(s,flush=True)
for nm,leg in (("NDX",r.USLeg("NDX",0.008,"QLD")),("S&P",r.USLeg("GSPC",0.018,"SSO"))):
    p(f"\n== 鄰近參數：台 w ＋ {nm} 2x 均線（全期 | 前段 | 後段 | 真實）==")
    for n,mo in ((150,False),(200,False),(250,False),(189,True),(210,True),(252,True)):
        s=sig(leg,n,mo)
        for w in (0.85,0.8,0.75,0.7,0.65):
            p(f"{nm} {'月底' if mo else '週五'} MA{n} 台{int(w*100)}% "+r.fmt(w,leg,None,sig_override=s))
leg=r.USLeg("NDX",0.008,"QLD"); s=sig(leg,210,True)
p("\n== 逐年：現行 vs 台80%＋NDX20% 10月線 vs 台80%＋現金20% ==")
a=r.run(1.0,None,None,"1998-01-01","2026-12-31")[2]
b=r.run(0.8,leg,None,"1998-01-01","2026-12-31",sig_override=s)[2]
c=r.run(0.8,None,None,"1998-01-01","2026-12-31")[2]
pa=pb=pc=1.0
for y in sorted(a):
    p(f"{y} 現行 {a[y]/pa-1:+7.1%}  分散 {b[y]/pb-1:+7.1%}  台80%現金 {c[y]/pc-1:+7.1%}")
    pa,pb,pc=a[y],b[y],c[y]
open('結果_研究09b_多市場鄰近參數.txt','w',encoding='utf-8').write("\n".join(L)+"\n")
