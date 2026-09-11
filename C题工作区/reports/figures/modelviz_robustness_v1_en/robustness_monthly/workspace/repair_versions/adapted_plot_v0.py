"""Adapt TRD_004 line/bar composition to main-policy monthly costs."""
import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

d=pd.read_csv(os.environ['DATA_PATH'],float_precision='round_trip');out=Path(os.environ['OUTPUT_DIR']);out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':12,'svg.fonttype':'none'})
x=np.arange(len(d));gain=d.cash_gain_yuan.to_numpy()/1000
fig,ax=plt.subplots(figsize=(11,5.8));right=ax.twinx();right.set_zorder(0);ax.set_zorder(1);ax.patch.set_visible(False)
right.bar(x,gain,width=.58,color=np.where(gain>=0,'#A9BBC8','#D4AC8F'),alpha=.75)
right.axhline(0,color='#999999',lw=.8);right.set_ylabel('Monthly savings (thousand CNY)',color='#676D73')
ax.plot(x,d.raw_total_cost_yuan/1e6,'o-',color='#3B6C8E',lw=2,ms=5)
ax.plot(x,d.corrected_total_cost_yuan/1e6,'s--',color='#CB8B52',lw=1.8,ms=4)
ax.set_ylabel('Actual monthly cost (million CNY)');ax.set_xticks(x,pd.to_datetime(d.month).dt.strftime('%b'));ax.set_xlabel('2025');ax.set_xlim(-.6,len(d)-.4)
ax.set_title('Main 28-day correction: monthly costs and savings',loc='left',fontsize=16,fontweight='bold',pad=56)
ax.text(0,1.16,f'Total saving: {d.cash_gain_yuan.sum():,.2f} CNY | Positive months: {int((gain>0).sum())} of {len(d)}',transform=ax.transAxes,fontsize=11,color='#555555')
ax.grid(axis='y',alpha=.17)
lo=min(-1.5,float(gain.min())*1.8);hi=max(2,float(gain.max())*1.4);right.set_ylim(lo,hi)
for xi,v in zip(x,gain):right.text(xi,v+(hi-lo)*.025 if v>=0 else v-(hi-lo)*.04,f'{v:,.2f}',ha='center',va='bottom' if v>=0 else 'top',fontsize=10,color='#555555')
handles=[Line2D([0],[0],color='#3B6C8E',marker='o',label='Raw PV'),Line2D([0],[0],color='#CB8B52',marker='s',ls='--',label='28-day correction'),Patch(facecolor='#A9BBC8',label='Savings (right axis)')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.845),ncol=3,frameon=False,fontsize=11)
fig.text(.5,.035,'Continuous state of charge from February; correction enabled on April 1. Negative months retained.',ha='center',fontsize=10,color='#555555')
fig.subplots_adjust(left=.10,right=.88,bottom=.16,top=.72)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg');plt.close(fig)
