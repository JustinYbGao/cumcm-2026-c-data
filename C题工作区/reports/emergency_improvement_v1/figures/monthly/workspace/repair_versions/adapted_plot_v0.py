"""TRD_004 paired line/bar grammar; exact months, no fitted trend."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

f=pd.read_csv(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
x=np.arange(len(f));months=pd.to_datetime(f.month).dt.strftime('%b')
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'svg.fonttype':'none','axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,1,figsize=(11,7.8),sharex=True);fig.subplots_adjust(left=.10,right=.88,top=.82,bottom=.18,hspace=.37)
blue='#3B6C8E';orange='#CB8B52';gray='#676D73'
for ax,b,title in zip(axes,['B0','B1'],['A | P versus frozen baseline B0','B | P versus seasonal baseline B1']):
    saving=(f[b]-f.P)/1000
    twin=ax.twinx();twin.spines['top'].set_visible(False)
    twin.bar(x,saving,width=.6,color=orange,alpha=.3);twin.axhline(0,color=orange,lw=.8)
    twin.set_ylim(-450,450);twin.set_ylabel('Savings (thousand CNY)',color='#9C6337')
    ax.plot(x,f[b]/1e6,color=gray,ls='--',marker='o',ms=3,lw=1.6)
    ax.plot(x,f.P/1e6,color=blue,marker='o',ms=3,lw=1.7)
    ax.set_ylabel('Actual cost (million CNY)');ax.grid(axis='y',alpha=.15)
    ax.set_zorder(twin.get_zorder()+1);ax.patch.set_visible(False)
    ax.set_title(title,loc='left',fontsize=11,pad=9)
    ax.text(.99,1.05,f'Total saving: {saving.sum()/1000:.3f} million CNY',transform=ax.transAxes,ha='right',va='bottom',fontsize=9)
axes[-1].set_xticks(x,months);axes[-1].set_xlabel('Evaluation month in 2025')
fig.suptitle('Monthly savings are positive against both Q2 baselines',x=.1,y=.965,ha='left',fontsize=15)
fig.legend(handles=[Line2D([],[],color=gray,ls='--',label='Matched baseline'),Line2D([],[],color=blue,label='P: risk purchase'),Patch(color=orange,alpha=.3,label='Baseline minus P')],loc='upper left',bbox_to_anchor=(.09,.922),ncol=3,frameon=False)
fig.text(.1,.083,'Monthly totals hide daily losses: P costs more on 97 days versus B0 and on 160 days versus B1.',fontsize=9)
fig.text(.1,.048,'Historical replay, February–December 2025. Lines: left axis. Savings bars: right axis; common scales.',fontsize=9)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg');plt.close(fig)
