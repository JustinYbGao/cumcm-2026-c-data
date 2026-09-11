"""CMP_003 stacked-column grammar adapted to exact Q2 cost components."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

f=pd.read_csv(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':11,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(11,6.5));fig.subplots_adjust(left=.09,right=.98,top=.78,bottom=.23)
x=np.arange(len(f));blue='#3B6C8E';orange='#CB8B52'
ax.axvspan(2.6,4.5,color='#EEE7E0',alpha=.45,zorder=0)
ax.bar(x,f.planned_cost_yuan/1e6,width=.64,color=blue,edgecolor='white',linewidth=1.2,label='Committed normal purchase')
ax.bar(x,f.emergency_cost_yuan/1e6,bottom=f.planned_cost_yuan/1e6,width=.64,color=orange,edgecolor='white',linewidth=1.2,label='Emergency purchase (full 5p)')
for i,row in f.iterrows():
    ax.text(i,row.total_cost_yuan/1e6+.4,f'{row.total_cost_yuan/1e6:.3f}',ha='center',fontsize=11,fontweight='bold' if row.policy=='P' else 'normal')
ax.set_xticks(x,['B0\nFrozen','B1\nSeasonal','P\nRisk purchase','E*\nReserve execution','PE*\nCombined'])
ax.set_ylabel('Actual total cost (million CNY)');ax.set_ylim(0,30);ax.set_xlim(-.6,4.6)
ax.set_yticks(np.arange(0,31,5));ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
ax.legend(loc='upper left',bbox_to_anchor=(0,1.16),ncol=2,frameon=False,fontsize=10)
fig.suptitle('Q2 risk purchase lowers the bill; reserve execution fails',x=.09,y=.96,ha='left',fontsize=15)
fig.text(.09,.90,'Historical replay | February–December 2025 | Common initial energy: 7,268.423 kWh',fontsize=10,color='#555555')
fig.text(.09,.115,'P: tau = 0.8, 28-day residual window; original point forecaster, greedy execution and terminal constraint.',fontsize=9)
fig.text(.09,.077,'* E and PE require discretionary discharge permission. Both increase the bill relative to B0 and B1.',fontsize=9)
fig.text(.09,.039,'Same fixed tariff, physical limits and initial state. Paid unused energy is fully charged; no sale revenue.',fontsize=9)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg');plt.close(fig)
