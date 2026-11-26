"""研究 172：日報各操作建議的勝率／期望值（使用者要求每個建議附部位、勝率、期望值）
V 爆量收黑加碼、F 外資期貨加碼：研究 141 引擎（台指期真實價、2018-06～、v3 在場）每筆不重疊；v3 主策略：1997～ 每段在場（2 倍日報酬）與空手期
用法：cd backtest && python -X utf8 research_172_各規則勝率期望值.py
"""
import importlib.util, os, sys
import numpy as np
HERE=os.getcwd(); sys.path.insert(0,HERE)
spec=importlib.util.spec_from_file_location("r141",os.path.join(HERE,"research_141_加碼總曝險上限.py")); R=importlib.util.module_from_spec(spec); spec.loader.exec_module(R)
bt=R.bt; R138=R.R138
T=R.build(); n=len(T); COST=3.0
def overlay(flag,H):
    res=[]; k=0
    while k<n-1:
        t=T[k]
        if t[flag] and t["st"]==1:
            j=k+1; e=T[j]["o"]; last=j
            for h in range(H):
                last=j+h
                if last>=n: last=n-1; break
                if T[last]["st"]==0: break
            res.append((T[last]["c"]-e-2*COST)/e)
            k=last+1
        else: k+=1
    return np.array(res)
for nm,f,H in (("V",'vsig',10),("F",'fsig',5)):
    x=overlay(f,H); print(nm,len(x),"win %.0f%%"%(np.mean(x>0)*100),"avg %+.2f%%"%(x.mean()*100),"avgwin %+.2f%% avgloss %+.2f%%"%(x[x>0].mean()*100,x[x<=0].mean()*100),"worst %+.1f%%"%(x.min()*100))
# v3 trades, full history, 2x daily TAIEX
ST=R138.ST; PX=bt.PX; D=bt.DAYS
trades=[];outs=[]
i=1; N=len(ST)
cur=None
for i in range(1,N-1):
    # held on day i+1 if ST[i]==1 (decided close i, executed close i+1 → return from day i+2); approximate: return day i+1 uses ST[i-1]
    pass
r1=np.array([0]+[PX[i]/PX[i-1]-1 for i in range(1,N)])
held=np.r_[0,0,np.array(ST[:-2])]  # 決定 i、i+1 收盤成交、i+2 起報酬
seg=[];state=held[0];start=0
for i in range(1,N):
    if held[i]!=state:
        seg.append((state,start,i-1)); state=held[i]; start=i
seg.append((state,start,N-1))
for s,a,b in seg:
    r=np.prod(1+2*r1[a:b+1])-1 if s==1 else np.prod(1+r1[a:b+1])-1
    (trades if s==1 else outs).append((D[a],r,b-a+1))
for lab,L in (("全期",trades),("2010~",[t for t in trades if t[0]>="2010"])):
    x=np.array([t[1] for t in L]); h=np.array([t[2] for t in L])
    print("v3",lab,len(x),"win %.0f%%"%(np.mean(x>0)*100),"avg %+.1f%% median %+.1f%%"%(x.mean()*100,np.median(x)*100),"avgwin %+.1f%% avgloss %+.1f%%"%(x[x>0].mean()*100,x[x<=0].mean()*100),"hold %d days"%np.median(h))
y=np.array([t[1] for t in outs]); print("空手期間指數(1x)",len(y),"avg %+.1f%%"%(y.mean()*100),"指數下跌比例 %.0f%%"%(np.mean(y<0)*100),"2x 避開 avg %+.1f%%"%(np.mean([ (1+t)**2-1 for t in y])*100))
