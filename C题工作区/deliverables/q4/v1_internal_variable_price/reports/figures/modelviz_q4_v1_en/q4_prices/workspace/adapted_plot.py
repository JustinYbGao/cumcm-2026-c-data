"""ModelViz TRD_004: line series and auxiliary error bars on four prescribed days."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

plt.rcParams.update({'font.family':['Times New Roman','DejaVu Serif'],'font.size':10,
    'axes.spines.top':False,'legend.frameon':False,'svg.hashsalt':'cumcm-q4-v1-en','savefig.facecolor':'white'})
d=pd.read_csv(sys.argv[1],float_precision='round_trip');out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21'];assert len(d)==576
fig,axes=plt.subplots(4,1,figsize=(11,10),sharex=True,layout='constrained')
fig.suptitle('Problem 4 | Causal price forecasts and realized prices',x=.07,y=.988,ha='left',fontsize=17)
limit=float(d[['price_actual_yuan_per_kwh','price_midnight_yuan_per_kwh','price_forecast_yuan_per_kwh']].to_numpy().max())*1.12
errlim=max(.02,float(np.abs(d.price_forecast_yuan_per_kwh-d.price_actual_yuan_per_kwh).max())*1.15)
facts=[]
for i,date in enumerate(dates):
    f=d.loc[d.date==date];edge=np.arange(145)/6;x=edge[:-1];a=axes[i];t=a.twinx()
    residual=f.price_forecast_yuan_per_kwh-f.price_actual_yuan_per_kwh
    t.bar(x,residual,width=1/6,align='edge',color='#c7dce9',alpha=.6,zorder=0)
    t.axhline(0,color='#aab5bf',lw=.5);t.set(ylabel='Forecast error (CNY/kWh)',ylim=(-errlim,errlim))
    a.set_zorder(t.get_zorder()+1);a.patch.set_visible(False)
    for column,color,style,lw in [('price_midnight_yuan_per_kwh','#d87928','--',1),('price_forecast_yuan_per_kwh','#1f78b4','-',1.4),('price_actual_yuan_per_kwh','#454b52','-',1)]:
        a.stairs(f[column].to_numpy(),edge,color=color,linestyle=style,lw=lw)
    a.set(ylabel='Price (CNY/kWh)',ylim=(0,limit),xlim=(0,24),xticks=[0,6,12,18,24])
    a.set_title(f'({chr(97+i)}) {date}',loc='left',fontsize=12,pad=7)
    for hour in [6,12,18]:a.axvline(hour,color='#9ca7b1',ls=':',lw=.7)
    a.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.6)
    facts.append({'date':date,'active_price_mae_yuan_per_kwh':float(residual.abs().mean())})
axes[-1].set_xlabel('Hour of day')
handles=[Line2D([],[],color='#454b52',label='Actual price'),Line2D([],[],color='#d87928',ls='--',label='Midnight OLS forecast'),
    Line2D([],[],color='#1f78b4',label='Active OLS forecast'),Patch(color='#c7dce9',label='Active forecast minus actual')]
fig.legend(handles=handles,ncol=4,loc='upper left',bbox_to_anchor=(.065,.952),fontsize=10)
fig.get_layout_engine().set(rect=(0,.06,1,.825))
fig.text(.07,.022,'All-update A policy. Actual prices are shown only for evaluation; future prices never enter the OLS fit.',fontsize=10,color='#59636f')
for ext in ['png','svg']:fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out.parent/'workspace/plot_facts.json').write_text(json.dumps({'rows':576,'dates':facts},indent=2)+'\n')
