"""Adapt CMP_005 horizontal gradient bars to paired monetary effects."""
import os
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.lines import Line2D

data=pd.read_csv(os.environ['DATA_PATH'],float_precision='round_trip')
out=Path(os.environ['OUTPUT_DIR']);out.mkdir(parents=True,exist_ok=True)
plt.rcParams.update({'font.family':'serif','font.serif':['Times New Roman','DejaVu Serif'],'font.size':12,'axes.labelsize':13,'svg.fonttype':'none'})
labels=['14-day window','28-day window (main)','56-day window','Higher efficiency / 28 days','Soft terminal / 28 days','Variable price / 28 days']
order=['fixed_w14_vs_raw','fixed_w28_vs_raw','fixed_w56_vs_raw','efficiency_w28_vs_raw','soft_w28_vs_raw','variable_w28_vs_raw']
d=data.set_index('comparison_id').loc[order];y=np.arange(len(d));cash=d.cash_gain_yuan.to_numpy()/1000
low=d.lower_95_yuan.to_numpy()/1000;high=d.upper_95_yuan.to_numpy()/1000
inventory=d.inventory_adjusted_gain_yuan.to_numpy()/1000
colors=LinearSegmentedColormap.from_list('teal_blue',['#66CDAA','#20B2AA','#008B8B','#4682B4','#000080','#191970'])(np.linspace(0,1,6))
fig,ax=plt.subplots(figsize=(11,6.5));ax.set_facecolor('#F5F5F5')
ax.barh(y,cash,height=.48,color=colors,edgecolor='#333333',linewidth=.7,zorder=2)
ax.hlines(y,low,high,color='#222222',lw=1.4,zorder=4);ax.vlines(low,y-.09,y+.09,color='#222222',lw=1.4,zorder=4);ax.vlines(high,y-.09,y+.09,color='#222222',lw=1.4,zorder=4)
ax.scatter(cash,y,color='white',edgecolors='black',s=27,zorder=5)
ax.scatter(inventory,y-.17,marker='D',s=24,facecolors='white',edgecolors='#555555',zorder=5)
ax.axvline(0,color='#777777',lw=1);ax.axhline(2.5,color='#AAAAAA',ls='--',lw=.8)
ax.set_yticks(y,labels);ax.invert_yaxis();ax.set_xlabel('Cost reduction vs matched raw PV (thousand CNY)')
ax.set_title('PV correction: window and assumption sensitivity',loc='left',fontsize=17,fontweight='bold',pad=43)
ax.text(0,1.045,'April–December 2025 | Each row uses its own matched baseline',transform=ax.transAxes,fontsize=11,color='#555555')
span=max(float(high.max()),float(cash.max()))-min(0,float(low.min()));ax.set_xlim(min(0,float(low.min()))-.07*span,max(float(high.max()),float(cash.max()))+.2*span)
for yi,v,hi in zip(y,cash,high):ax.text(max(v,hi)+.035*span,yi,f'{v:,.2f}',va='center',fontsize=11)
ax.grid(axis='x',color='white',lw=1.5,zorder=0);ax.set_axisbelow(True);ax.tick_params(length=0)
for sp in ax.spines.values():sp.set_visible(False)
handles=[Line2D([0],[0],marker='o',markerfacecolor='white',color='#222222',label='Cash gain and 95% resampling interval'),Line2D([0],[0],marker='D',markerfacecolor='white',color='#555555',linestyle='None',label='Inventory-adjusted gain')]
fig.legend(handles=handles,loc='lower center',bbox_to_anchor=(.52,.07),frameon=False,ncol=1,fontsize=10)
fig.text(.5,.025,'Intervals: 7-day blocks within months, 5,000 resamples. Historical variability; no future guarantee.',ha='center',fontsize=10,color='#555555')
fig.subplots_adjust(left=.29,right=.97,bottom=.25,top=.81)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg');plt.close(fig)
