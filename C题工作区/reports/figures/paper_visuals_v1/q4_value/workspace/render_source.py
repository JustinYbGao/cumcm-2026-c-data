"""ModelViz TRD_004 line-bar grammar and blue/orange palette, without fitted trends."""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({'font.family':['Times New Roman','DejaVu Serif'],'font.size':11,
    'axes.spines.top':False,'axes.spines.right':False,'legend.frameon':False,
    'svg.hashsalt':'cumcm-q4-v1-en','savefig.facecolor':'white'})
d=pd.read_csv(sys.argv[1],float_precision='round_trip');out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
assert d.month.tolist()==[f'2025-{i:02d}' for i in range(2,13)]
x=np.arange(11)
fig,ax=plt.subplots(2,1,figsize=(10.5,7.5),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2,1]})
fig.suptitle('Problem 4 | Value of adapting to variable prices',x=.075,y=.985,ha='left',fontsize=17)
for fixed,ols,color,label in [('q42_fixed','q42_ols','#1f78b4','Day-ahead'),('q43_all_A_fixed','q43_all_A_ols','#d87928','All updates, A')]:
    ax[0].plot(x,d[fixed+'_cost_yuan']/1e6,ls='--',lw=1.3,color=color,alpha=.65,label=label+': fixed-price input')
    ax[0].plot(x,d[ols+'_cost_yuan']/1e6,'o-',ms=4,lw=1.5,color=color,label=label+': OLS price input')
ax[0].set(ylabel='Actual cost (million CNY)',ylim=(0,float(d.filter(like='_cost_yuan').to_numpy().max()/1e6)*1.3))
ax[0].set_title('(a) All policies are billed at actual variable prices',loc='left',fontsize=12,pad=8)
ax[0].legend(ncol=2,loc='upper left',fontsize=10)
ax[1].bar(x-.17,d.q42_saving_yuan/1000,.32,color='#a6cee3',label='Day-ahead')
ax[1].bar(x+.17,d.q43_saving_yuan/1000,.32,color='#fdbf6f',label='All updates, A')
ax[1].axhline(0,color='#555555',lw=.8)
ax[1].set(ylabel='Savings (thousand CNY)',xlabel='Month (2025)',xticks=x,xticklabels=['Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'])
ax[1].set_title('(b) Fixed-price input minus OLS input: positive means lower actual cost',loc='left',fontsize=11.5,pad=8)
for a in ax:a.set_axisbelow(True);a.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.7);a.set_xlim(-.65,10.65)
fig.get_layout_engine().set(rect=(0,.08,1,.85))
fig.text(.075,.025,'Same tariff for settlement; only the planning price input changes within each branch. Internal assumptions.',fontsize=9.5,color='#59636f')
for ext in ['png','svg']:fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out.parent/'workspace/plot_facts.json').write_text(json.dumps({'monthly_rows':11,'q42_saving_yuan':float(d.q42_saving_yuan.sum()),'q43_saving_yuan':float(d.q43_saving_yuan.sum())},indent=2)+'\n')
