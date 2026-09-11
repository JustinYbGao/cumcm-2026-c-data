"""ModelViz CMP-005: repeated horizontal gradient bars for exact bill differences."""
import os
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import pandas as pd

source=Path(os.environ.get('DATA_PATH',sys.argv[1] if len(sys.argv)>1 else 'data.csv'))
out=Path(os.environ.get('OUTPUT_DIR',sys.argv[2] if len(sys.argv)>2 else 'outputs'));out.mkdir(parents=True,exist_ok=True)
f=pd.read_csv(source,float_precision='round_trip');assert len(f)==18
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':11,'svg.fonttype':'none'})
fig,axes=plt.subplots(1,3,figsize=(16,10),sharey=True)
fig.subplots_adjust(left=.205,right=.98,bottom=.12,top=.87,wspace=.18)
cmap=LinearSegmentedColormap.from_list('template_gradient',['#66CDAA','#20B2AA','#008B8B','#4682B4','#000080','#191970'])
colors=cmap(np.linspace(0,1,len(f)));y=np.arange(len(f))
fields=['ordinary_saving_vs_P_floor_yuan','emergency_saving_vs_P_floor_yuan','total_saving_vs_P_floor_yuan']
for i,(ax,col,title) in enumerate(zip(axes,fields,['(a) Ordinary purchase savings','(b) Emergency purchase savings','(c) Total savings'])):
    ax.set_facecolor('#F5F5F5');values=f[col].to_numpy()/1000
    bars=ax.barh(y,values,color=colors,edgecolor='#253741',linewidth=.6,height=.72,zorder=3)
    for j,b in enumerate(bars):
        if f.emergency_cost_yuan.iloc[j]>1e6+1e-5:b.set_hatch('///')
    span=max(values.max(),0)-min(values.min(),0);pad=max(span*.022,.7)
    for j,v in enumerate(values):ax.text(v+(pad if v>=0 else -pad),j,f'{v:+.2f}',ha='left' if v>=0 else 'right',va='center',fontsize=9)
    ax.set_xlim(min(values.min(),0)-span*.24-pad,max(values.max(),0)+span*.26+pad)
    ax.axvline(0,color='#484848',linewidth=.8,zorder=4)
    ax.axhline(9.5,color='#919191',linestyle='--',linewidth=.8)
    ax.set_title(title,fontsize=13,fontweight='bold',pad=12)
    ax.set_xlabel('Savings vs P_floor (thousand CNY)',fontsize=10)
    ax.set_yticks(y,labels=f.policy.tolist());ax.grid(axis='x',color='white',linewidth=1.5,zorder=0)
    ax.tick_params(length=0)
    for spine in ax.spines.values():spine.set_visible(False)
axes[0].invert_yaxis()
fig.suptitle('Q2: less ordinary purchasing can increase the emergency bill',fontsize=19,fontweight='bold',y=.97)
fig.text(.205,.917,'All 18 new policies | 334-day historical replay | Positive values mean lower cost',fontsize=12)
fig.text(.205,.062,'Dashed row: eight follow-up profiles. Hatched bars: emergency bill exceeds the 1,000,000 CNY cap.',fontsize=11)
fig.text(.205,.035,'The cap is checked on the observed year; no future cap guarantee. Panel ranges differ; units are identical.',fontsize=10,color='#555555')
for ext in ['png','svg']:fig.savefig(out/('chart.'+ext),dpi=300,metadata={'Creator':'Q2 ModelViz adaptation'} if ext=='svg' else None)
plt.close(fig)
