"""ModelViz TRD-004: observed monthly paired savings, bar plus unfit marker lines."""
import os
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
source=Path(os.environ.get('DATA_PATH',sys.argv[1] if len(sys.argv)>1 else 'data.csv'))
out=Path(os.environ.get('OUTPUT_DIR',sys.argv[2] if len(sys.argv)>2 else 'outputs'));out.mkdir(parents=True,exist_ok=True)
f=pd.read_csv(source,float_precision='round_trip');assert len(f)==11
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':12,'svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(13,6.8));fig.subplots_adjust(left=.1,right=.97,bottom=.18,top=.75)
x=np.arange(len(f));policies=list(f.columns[1:]);best=policies[0]
ax.bar(x,f[best]/1000,width=.62,color='#b3cde3',edgecolor='#377eb8',label=best,zorder=2)
colors=['#b8a32f','#228B22','#8b7d7d'];marks=['o','s','D']
for policy,color,mark in zip(policies[1:],colors,marks):ax.plot(x,f[policy]/1000,color=color,marker=mark,linewidth=1.7,markersize=5,label=policy,zorder=3)
ax.axhline(0,color='#333333',linewidth=.9);ax.grid(axis='y',alpha=.3);ax.set_axisbelow(True)
ax.set_xticks(x,labels=pd.to_datetime(f.month).dt.strftime('%b'));ax.set_xlabel('2025')
ax.set_ylabel('Total savings vs v3 best (thousand CNY)')
ax.spines['top'].set_visible(False);ax.spines['right'].set_visible(False)
fig.suptitle('Monthly cost savings and losses',fontsize=19,fontweight='bold',y=.96)
fig.legend(*ax.get_legend_handles_labels(),loc='upper center',bbox_to_anchor=(.54,.89),ncol=4,frameon=False,fontsize=11)
fig.text(.1,.065,'Positive = lower actual total bill. Best observed eligible policy is selected after historical replay.',fontsize=11)
fig.text(.1,.03,'No fitted trend, no smoothing, no independent-year performance claim.',fontsize=10,color='#555555')
for ext in ['png','svg']:fig.savefig(out/('chart.'+ext),dpi=300,metadata={'Creator':'Q2 ModelViz adaptation'} if ext=='svg' else None)
plt.close(fig)
