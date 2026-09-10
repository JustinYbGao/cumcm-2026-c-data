"""ModelViz TRD_001: serif dual-axis time series with muted fill and interval bars.
Replicate the grammar over four prescribed days; no smoothing of commitments.
"""
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
    'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
    'axes.linewidth':.8,'legend.frameon':False,'svg.hashsalt':'cumcm-q3-v1-en','savefig.facecolor':'white'})
d=pd.read_csv(sys.argv[1],float_precision='round_trip');out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21'];assert len(d)==576
fig,axes=plt.subplots(4,2,figsize=(12,10),layout='constrained',sharex=True)
fig.suptitle('Problem 3 | Revised commitments and actual battery operation',x=.065,y=.987,ha='left',fontsize=17)
qmax=float(d[['grid_original_kwh','grid_effective_kwh']].to_numpy().max()/1000)
emax=max(.05,float(d.emergency_kwh.max()/1000)*1.25)
facts=[]
for row,date in enumerate(dates):
    f=d.loc[d.date==date];assert f.slot_id.tolist()==list(range(1,145))
    edge=np.arange(145)/6;x=edge[:-1]
    ax,st=axes[row]
    ax.stairs(f.grid_original_kwh.to_numpy()/1000,edge,color='#777777',lw=1,linestyle='--')
    ax.stairs(f.grid_effective_kwh.to_numpy()/1000,edge,color='#1f78b4',lw=1.15)
    ax.set(ylabel='Grid energy (MWh / 10 min)',ylim=(0,qmax*1.14))
    ax.set_title(f'({chr(97+row*2)}) {date} | Commitment',loc='left',fontsize=11,pad=7)
    state=np.r_[f.energy_start_actual_kwh.iloc[0],f.energy_end_actual_kwh.to_numpy()]/1000
    st.fill_between(edge,1.2,state,color='#a8edea',alpha=.45)
    st.plot(edge,state,color='#307f80',lw=1.4)
    st.axhline(1.2,color='#777777',ls=':',lw=.7);st.axhline(10.8,color='#777777',ls=':',lw=.7)
    st.set(ylabel='Stored energy (MWh)',ylim=(0,12),yticks=[1.2,6,10.8])
    twin=st.twinx();twin.spines['right'].set_visible(True)
    twin.bar(x,f.emergency_kwh/1000,width=1/6,align='edge',color='#cf7957',alpha=.75)
    twin.set(ylabel='Emergency (MWh / 10 min)',ylim=(0,emax));twin.tick_params(axis='y',labelsize=9,colors='#986247')
    st.set_title(f'({chr(98+row*2)}) {date} | Actual state and shortage',loc='left',fontsize=11,pad=7)
    for a in [ax,st]:
        for hour in [6,12,18]:a.axvline(hour,color='#b9c2cb',ls=':',lw=.8)
        a.set(xlim=(0,24),xticks=[0,6,12,18,24]);a.set_axisbelow(True)
        a.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.7);a.tick_params(direction='in')
    facts.append({'date':date,'emergency_kwh':float(f.emergency_kwh.sum()),'total_cost_yuan':float(f.total_cost_yuan.sum())})
for a in axes[-1]:a.set_xlabel('Hour of day')
handles=[Line2D([],[],color='#777777',ls='--',label='Midnight commitment'),Line2D([],[],color='#1f78b4',label='Final effective commitment'),
    Line2D([],[],color='#307f80',label='Actual stored energy'),Patch(color='#cf7957',alpha=.75,label='Emergency purchase')]
fig.legend(handles=handles,loc='upper left',bbox_to_anchor=(.065,.955),ncol=4,fontsize=10)
fig.get_layout_engine().set(rect=(0,.065,1,.89))
fig.text(.065,.025,'Refund A; all updates. Dotted vertical lines mark 06:00, 12:00 and 18:00. Internal interval-end assumption.',fontsize=10,color='#59636f')
for ext in ['png','svg']:fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out.parent/'workspace/plot_facts.json').write_text(json.dumps({'rows':576,'dates':facts},indent=2)+'\n')
