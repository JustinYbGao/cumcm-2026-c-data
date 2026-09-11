"""Observed prefix risk and causal quantile estimates without smoothing."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
p=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
f=pd.read_csv(p);x=pd.to_datetime(f.date);actual=f.observed_prefix_kwh/1000;pred=f.forecast_prefix_kwh/1000;gap=np.maximum(actual-pred,0)
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':11,'axes.spines.top':False,'svg.fonttype':'none'})
fig,ax=plt.subplots(figsize=(11,6.5));fig.subplots_adjust(left=.09,right=.90,top=.77,bottom=.17);other=ax.twinx()
blue='#3B6C8E';orange='#CB8B52';gray='#676D73'
other.bar(x,gap,color=orange,alpha=.28,width=.85);other.set_ylabel('Positive underprediction (MWh)',color='#9C6337')
ax.plot(x,actual,color=gray,lw=1.0);ax.plot(x,pred,color=blue,lw=1.3)
ax.set_ylabel('Maximum cumulative prefix (MWh)');ax.set_xlabel('Evaluation date in 2025');ax.grid(axis='y',alpha=.15)
ax.xaxis.set_major_locator(mdates.MonthLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
limit=max(float(actual.max()),float(pred.max()),.1)*1.08;ax.set_ylim(0,limit);other.set_ylim(0,max(float(gap.max()),.1)*1.15)
ax.set_zorder(other.get_zorder()+1);ax.patch.set_visible(False)
fig.suptitle('Continuous net-load risk: observed versus causal forecast',y=.95,fontsize=14)
fig.text(.5,.885,f'Noon–18:00 window  |  Quantile target: 0.75  |  Observed coverage: {(actual<=pred+1e-9).mean():.3f}',ha='center',fontsize=10)
fig.legend(handles=[Line2D([],[],color=gray,label='Observed prefix risk'),Line2D([],[],color=blue,label='Causal quantile forecast'),Patch(color=orange,alpha=.28,label='Positive underprediction')],loc='upper center',bbox_to_anchor=(.5,.85),ncol=3,frameon=False,fontsize=9)
fig.text(.09,.07,'Forecasts use completed historical days only. Original daily observations; no smoothing or time shift.',fontsize=8)
fig.text(.09,.045,'Risk is a planning feature, not a required battery capacity or a joint safety guarantee. Internal assumptions.',fontsize=8)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg');plt.close(fig)
