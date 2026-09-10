"""ModelViz TRD_004: blue/orange/gray line-bar composition, shared monthly axis."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({'font.family':['Times New Roman','DejaVu Serif'],'font.size':11,
    'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
    'axes.linewidth':.8,'legend.frameon':False,'svg.hashsalt':'cumcm-q3-v1-en','savefig.facecolor':'white'})
d=pd.read_csv(sys.argv[1],float_precision='round_trip');out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
assert d.month.tolist()==[f'2025-{i:02d}' for i in range(2,13)]
for policy in ['all_A','all_B']:
    assert np.allclose(d.no_update_total_cost_yuan-d[policy+'_total_cost_yuan'],d[policy+'_saving_yuan'],atol=1e-6,rtol=0)
x=np.arange(11)
fig,ax=plt.subplots(2,1,figsize=(10.5,7.5),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2,1]})
fig.suptitle('Problem 3 | Costs under forecast-update policies',x=.075,y=.985,ha='left',fontsize=17)
ax[0].bar(x,d.no_update_total_cost_yuan/1e6,.58,color='#dddddd',edgecolor='white',label='Midnight only')
ax[0].plot(x,d.all_A_total_cost_yuan/1e6,'o-',color='#ff7f00',ms=5,lw=1.5,label='All updates: refund A')
ax[0].plot(x,d.all_B_total_cost_yuan/1e6,'x--',color='#1f78b4',ms=6,lw=1.4,label='All updates: no refund B')
ax[0].set(ylabel='Actual cost (million CNY)',ylim=(0,2.1))
ax[0].set_title('(a) Contract and emergency costs combined',loc='left',fontsize=12,pad=10)
ax[0].legend(loc='upper left',ncol=3,fontsize=10)
totals=[d[c+'_total_cost_yuan'].sum()/1e6 for c in ['no_update','all_A','all_B']]
ax[0].text(.02,.80,f'Feb-Dec (million CNY): midnight {totals[0]:.3f} | A {totals[1]:.3f} | B {totals[2]:.3f}',transform=ax[0].transAxes,fontsize=10,color='#555555')
ax[1].bar(x-.17,d.all_A_saving_yuan/1000,.32,color='#fdbf6f',label='Refund A')
ax[1].bar(x+.17,d.all_B_saving_yuan/1000,.32,color='#a6cee3',label='No refund B')
ax[1].axhline(0,color='#555555',lw=.7)
ax[1].set(ylabel='Savings (thousand CNY)',xlabel='Month (2025)',xticks=x,
    xticklabels=['Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
ax[1].set_title('(b) Savings relative to midnight-only control',loc='left',fontsize=12,pad=9)
for a in ax:
    a.set_xlim(-.65,10.65);a.set_axisbelow(True);a.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.8);a.tick_params(direction='in')
fig.get_layout_engine().set(rect=(0,.09,1,.85))
fig.text(.075,.048,'Updates at 06:00, 12:00 and 18:00. Same load forecasts and execution rule; each policy has its own state path.',fontsize=9.5,color='#59636f')
fig.text(.075,.022,'Final volume is billed once against the midnight plan. Internal settlement assumptions; A and B nearly overlap.',fontsize=9.5,color='#59636f')
for ext in ['png','svg']:fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out.parent/'workspace/plot_facts.json').write_text(json.dumps({'months':11,'annual_costs_yuan':dict(zip(['no_update','all_A','all_B'],[float(t*1e6) for t in totals]))},indent=2)+'\n')
