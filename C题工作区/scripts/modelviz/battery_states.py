"""Adapted from ModelViz 12_TRD_004: paired time series and auxiliary difference.
Retains scheme 2 blue/orange/gray, serif type, light y-grid and panel letters.
No regression, smoothing, resampling or data shift is applied.
"""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

plt.rcParams.update({'font.family':['Times New Roman','DejaVu Serif'], 'font.size':11,
    'axes.unicode_minus':False, 'axes.spines.top':False, 'axes.spines.right':False,
    'axes.linewidth':.8, 'axes.labelpad':8, 'legend.frameon':False,
    'svg.hashsalt':'cumcm-modelviz-v3-en', 'savefig.facecolor':'white'})
data = pd.read_csv(sys.argv[1], float_precision='round_trip')
out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
assert len(data)==145 and np.array_equal(data.minute, np.arange(145)*10)
x=data.minute/60
a=data.baseline_energy_kwh/1000
b=data.roundtrip_energy_kwh/1000
fig, axes=plt.subplots(2,1,figsize=(10.2,6.7),sharex=True,
    gridspec_kw={'height_ratios':[3,1]},layout='constrained')
fig.suptitle('Problem 1 | Efficiency assumptions and stored energy',fontsize=17,y=.985,x=.08,ha='left')
ax=axes[0]
ax.axhspan(1.2,10.8,color='#f4f6f8',zorder=0)
ax.plot(x,a,color='#1f78b4',lw=2,label='90% per direction (baseline)')
ax.plot(x,b,color='#ff7f00',lw=1.8,ls='--',label='90% round-trip (sensitivity)')
for level,label in [(1.2,'Lower bound: 1.2 MWh'),(10.8,'Upper bound: 10.8 MWh')]:
    ax.axhline(level,color='#8a939d',lw=.8,ls=(0,(4,3)))
    ax.text(23.8 if level>6 else .25,level+.15,label,ha='right' if level>6 else 'left',va='bottom',color='#606872',fontsize=10)
ax.scatter([0,24],[a.iloc[0],a.iloc[-1]],s=26,facecolor='white',edgecolor='#1f78b4',zorder=5)
ax.set(ylabel='Stored energy (MWh)',ylim=(0,12.7),yticks=[0,1.2,3,6,9,10.8,12])
ax.set_title('(a) Optimal storage trajectories',loc='left',fontsize=12,pad=9)
ax.legend(loc='upper center',ncol=2,fontsize=10,bbox_to_anchor=(.5,1.02))
delta=b-a
axes[1].fill_between(x,delta,0,color='#a6cee3',alpha=.7)
axes[1].plot(x,delta,color='#555555',lw=1.1)
axes[1].axhline(0,color='#68717c',lw=.7)
axes[1].set(ylabel='Energy difference (MWh)',xlabel='Time of day (h)',xlim=(0,24),xticks=range(0,25,2))
axes[1].set_title('(b) 90% round-trip minus baseline',loc='left',fontsize=12,pad=9)
for ax in axes:
    ax.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.7)
    ax.tick_params(direction='in',length=4)
fig.get_layout_engine().set(rect=(0,.07,1,.84))
fig.text(.08,.022,'Internal interval-end assumption; 145 original state points; lines connect adjacent states.',fontsize=10,color='#59636f')
for ext in ['png','svg']:
    fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out.parent/'workspace/plot_facts.json').write_text(json.dumps({'rows':len(data),'state_points':145,
    'max_abs_difference_kwh':float(abs(delta).max()*1000),'start_hour':float(x.iloc[0]),'end_hour':float(x.iloc[-1])},indent=2)+'\n')
