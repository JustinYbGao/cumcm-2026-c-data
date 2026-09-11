"""TRD_004 observed paired lines and difference bars, including losses."""
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
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'svg.fonttype':'none','svg.hashsalt':'q2_cost_aware_v2','axes.spines.top':False,'axes.spines.right':False})
fig,axes=plt.subplots(2,1,figsize=(11,8));fig.subplots_adjust(left=.10,right=.88,top=.82,bottom=.19,hspace=.39)
blue='#3B6C8E';orange='#CB8B52';gray='#676D73'
limit=np.ceil(max(abs(f.P-f.P_floor).max(),abs(f.P_floor-f.S_joint).max())/10000)*10
for ax,b,target,title in zip(axes,['P','P_floor'],['P_floor','S_joint'],['A | Fixed floor versus prior risk policy','B | Joint selection versus fixed floor']):
    saving=(f[b]-f[target])/1000;twin=ax.twinx();twin.spines['top'].set_visible(False)
    twin.bar(x,saving,width=.6,color=orange,alpha=.33);twin.axhline(0,color=orange,lw=.8)
    twin.set_ylim(-limit,limit);twin.set_ylabel('Savings (thousand CNY)',color='#9C6337')
    ax.plot(x,f[b]/1e6,color=gray,ls='--',marker='o',ms=3,lw=1.6)
    ax.plot(x,f[target]/1e6,color=blue,marker='o',ms=3,lw=1.7)
    ax.set_ylabel('Actual cost (million CNY)');ax.grid(axis='y',alpha=.15)
    ax.set_zorder(twin.get_zorder()+1);ax.patch.set_visible(False)
    ax.set_title(title,loc='left',fontsize=11,pad=10)
    ax.text(.99,1.05,f'Total saving: {saving.sum():+.1f} thousand CNY',transform=ax.transAxes,ha='right',va='bottom',fontsize=9)
axes[-1].set_xticks(x,months);axes[-1].set_xlabel('Evaluation month in 2025')
fig.suptitle('Monthly evidence includes cost increases',x=.1,y=.965,ha='left',fontsize=15)
fig.legend(handles=[Line2D([],[],color=gray,ls='--',label='Reference policy'),Line2D([],[],color=blue,label='Compared policy'),Patch(color=orange,alpha=.33,label='Reference minus compared')],loc='upper left',bbox_to_anchor=(.09,.922),ncol=3,frameon=False)
fig.text(.1,.092,'P_floor loses on 32 of 334 days versus P, despite savings in every evaluated month.',fontsize=9)
fig.text(.1,.052,'Lines use left axes; bars use right axes with a common savings scale. Negative bars mean higher cost.',fontsize=9)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg',metadata={'Date':None});plt.close(fig)
