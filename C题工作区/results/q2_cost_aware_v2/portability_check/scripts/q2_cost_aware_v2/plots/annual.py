"""CMP_003 categorical stacks adapted to actual Q2 bills and certified bound."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

f=pd.read_csv(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'svg.fonttype':'none','svg.hashsalt':'q2_cost_aware_v2','axes.spines.top':False,'axes.spines.right':False})
fig,ax=plt.subplots(figsize=(12,7));fig.subplots_adjust(left=.08,right=.98,top=.79,bottom=.25)
x=np.arange(len(f));blue='#3B6C8E';orange='#CB8B52'
ax.bar(x,f.planned_cost_yuan/1e6,width=.67,color=blue,edgecolor='white',linewidth=1.1,label='Committed normal purchase')
ax.bar(x,f.emergency_cost_yuan/1e6,bottom=f.planned_cost_yuan/1e6,width=.67,color=orange,edgecolor='white',linewidth=1.1,label='Emergency purchase (full 5p)')
bound=f.relaxed_lower_bound_yuan.iloc[0]/1e6
ax.axhline(bound,color='#963C3C',ls='--',lw=1.4,label=f'Relaxed foresight bound: {bound:.3f}')
for i,r in f.iterrows():
    ax.text(i,r.total_cost_yuan/1e6+.20,f'{r.total_cost_yuan/1e6:.3f}',ha='center',fontsize=9,fontweight='bold' if r.policy=='P_floor' else 'normal')
ax.set_xticks(x,['B0\nFrozen','B1\nSeasonal','P\nPrior risk','P_terminal\nFixed 6000','P_floor\nFixed 1200','S_terminal\nSelect target','S_joint\nJoint select','P_B1\nSeasonal risk','P_B1_floor\nSeasonal floor'])
ax.set_ylabel('Actual total cost (million CNY)');ax.set_ylim(0,18);ax.set_xlim(-.6,8.6)
ax.set_yticks(np.arange(0,19,3));ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
ax.legend(loc='upper left',bbox_to_anchor=(0,1.16),ncol=2,frameon=False,fontsize=9)
fig.suptitle('Lower terminal targets help; joint selection adds no saving',x=.08,y=.965,ha='left',fontsize=15)
fig.text(.08,.91,'Historical replay | Feb–Dec 2025 | 334 days | Same initial energy: 7,268.423 kWh',fontsize=10,color='#555555')
fig.text(.08,.135,'P_floor saves CNY 186,671 versus P. S_terminal improves on P_floor by only CNY 1,161.',fontsize=10)
fig.text(.08,.090,'The dashed line relaxes information and operating constraints; its gap is not an achievable saving.',fontsize=9)
fig.text(.08,.048,'Nine displayed policies; all 13 controls and sensitivity results remain in the accompanying comparison table.',fontsize=9)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg',metadata={'Date':None});plt.close(fig)
