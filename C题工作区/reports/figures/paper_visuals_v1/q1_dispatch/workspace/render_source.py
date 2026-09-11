"""Adapt ModelViz 12_TRD_001 storage power bars and capacity line; add flow/price panels.
Retains dual-axis storage panel, signed bars, circular state markers and inward ticks.
"""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({'font.family':['Times New Roman','DejaVu Serif'], 'font.size':11,
    'axes.unicode_minus':False, 'axes.spines.top':False, 'axes.spines.right':False,
    'axes.linewidth':.8,'axes.labelpad':8,'legend.frameon':False,
    'svg.hashsalt':'cumcm-modelviz-v3-en','savefig.facecolor':'white'})
d=pd.read_csv(sys.argv[1],float_precision='round_trip')
out=Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
assert len(d)==144 and np.array_equal(d.start_minute,np.arange(144)*10)
edges=np.r_[d.start_minute.to_numpy(),d.end_minute.iloc[-1]]/60
x=edges[:-1]
fig,axes=plt.subplots(3,1,figsize=(10.7,9),sharex=True,layout='constrained',
    gridspec_kw={'height_ratios':[1.35,1.3,.7]})
fig.suptitle('Problem 1 | Grid purchases, storage and electricity price',fontsize=17,y=.985,x=.075,ha='left')
for column,label,color in [('load_kw','Load','#3d4854'),('pv_forecast_kw','Given PV forecast','#cda340'),('grid_kwh','Planned grid purchase','#1f78b4')]:
    values=d[column]/1000*(6 if column=='grid_kwh' else 1)
    axes[0].stairs(values,edges,color=color,label=label,baseline=None,lw=1.5)
axes[0].set(ylabel='AC power (MW)',ylim=(0,10.6))
axes[0].set_title('(a) Load, PV and planned grid purchases',loc='left',fontsize=12,pad=10)
axes[0].legend(ncol=3,loc='upper left',fontsize=10)
axes[1].bar(x,d.charge_kwh*6/1000,width=1/6,align='edge',color='#a6cee3',label='Charging (+)',zorder=2)
axes[1].bar(x,-d.discharge_kwh*6/1000,width=1/6,align='edge',color='#cab2d6',label='Discharging (-)',zorder=2)
axes[1].axhline(0,color='#59636f',lw=.7)
for value in [-5,5]: axes[1].axhline(value,color='#9ba4ad',lw=.7,ls=(0,(4,3)))
axes[1].set(ylabel='Battery AC power (MW)',ylim=(-6.5,7.5),yticks=[-5,0,5])
axes[1].set_title('(b) Battery power and stored energy (power limits: ±5 MW)',loc='left',fontsize=12,pad=10)
twin=axes[1].twinx()
twin.spines['right'].set_visible(True)
state=np.r_[d.energy_start_kwh.iloc[0],d.energy_end_kwh]/1000
twin.plot(edges,state,color='#b5544a',lw=1.6,marker='o',markevery=12,ms=3.5,mfc='white',label='Stored energy (right axis)')
twin.set(ylabel='Stored energy (MWh)',ylim=(0,15),yticks=[0,3,6,9,12])
twin.tick_params(axis='y',colors='#9a4a43',direction='in')
twin.yaxis.label.set_color('#9a4a43')
h,l=axes[1].get_legend_handles_labels(); h2,l2=twin.get_legend_handles_labels()
axes[1].legend(h+h2,l+l2,ncol=3,loc='upper left',fontsize=10)
axes[2].stairs(d.price_yuan_per_kwh,edges,color='#6a3d9a',baseline=None,lw=1.8)
axes[2].set(ylabel='Price (CNY/kWh)',ylim=(0,1.55),yticks=[0,.5,1,1.5],xlabel='Time of day (h)')
axes[2].set_title('(c) Known electricity price',loc='left',fontsize=12,pad=10)
for ax in axes:
    ax.set(xlim=(0,24),xticks=range(0,25,2))
    ax.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.7)
    ax.tick_params(direction='in')
fig.get_layout_engine().set(rect=(0,.055,1,.86))
fig.text(.075,.018,'Baseline: 90% efficiency per direction. Internal interval-end assumption; 144 ten-minute intervals.',fontsize=10,color='#59636f')
for ext in ['png','svg']:
    fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out.parent/'workspace/plot_facts.json').write_text(json.dumps({'intervals':len(d),'state_points':len(state),
    'grid_kwh':float(d.grid_kwh.sum()),'cost_yuan':float(d.cost_yuan.sum()),
    'maximum_power_mw':float(max(d.load_kw.max(),d.pv_forecast_kw.max(),d.grid_kwh.max()*6)/1000)},indent=2)+'\n')
