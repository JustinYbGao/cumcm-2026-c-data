"""Adapt ModelViz 12_TRD_001 dual-axis state/energy combination to four date facets.
Use fixed scales across all days and original interval widths, without smoothing.
"""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Songti.ttc')
plt.rcParams.update({'font.family':['Times New Roman','Songti SC'],'font.size':11,
    'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
    'axes.linewidth':.8,'axes.labelpad':8,'legend.frameon':False,
    'svg.hashsalt':'cumcm-modelviz-v2','savefig.facecolor':'white'})
d=pd.read_csv(sys.argv[1],float_precision='round_trip')
out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
dates=['2025-03-20','2025-06-21','2025-09-23','2025-12-21']
fig,axes=plt.subplots(4,1,figsize=(10.5,10.5),sharex=True,layout='constrained')
fig.suptitle('问题2  |  指定日的储能执行与紧急购电',fontsize=17,x=.075,ha='left')
facts={}
for i,(ax,date) in enumerate(zip(axes,dates)):
    f=d.loc[d.date==date]
    assert len(f)==144 and np.array_equal(f.slot_id,np.arange(1,145))
    edges=np.arange(145)/6
    actual=np.r_[f.energy_start_actual_kwh.iloc[0],f.energy_end_actual_kwh]/1000
    plan=np.r_[f.energy_start_plan_kwh.iloc[0],f.energy_end_plan_kwh]/1000
    # Bars on the base axes remain behind the transparent state axes.
    ax.bar(edges[:-1],f.emergency_kwh,width=1/6,align='edge',color='#fdbf6f',alpha=.75)
    ax.yaxis.tick_right();ax.yaxis.set_label_position('right')
    ax.spines['right'].set_visible(True);ax.spines['left'].set_visible(False)
    ax.set(ylabel='紧急购电 / kWh',ylim=(0,1000),yticks=[0,500,1000])
    ax.tick_params(axis='y',colors='#a46420');ax.yaxis.label.set_color('#a46420')
    state=ax.twinx()
    state.yaxis.tick_left();state.yaxis.set_label_position('left')
    state.spines['right'].set_visible(False);state.spines['left'].set_visible(True)
    state.plot(edges,plan,color='#7a828d',lw=1.35,ls=(0,(4,2)))
    state.plot(edges,actual,color='#1f78b4',lw=1.8)
    for value in [1.2,10.8]:state.axhline(value,color='#aeb8c2',ls=(0,(2,3)),lw=.7)
    state.set(ylabel='储能电量 / MWh',ylim=(0,12),yticks=[0,3,6,9,12])
    state.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.6)
    state.tick_params(direction='in')
    ax.set_title(f'({chr(97+i)}) {date}    紧急购电合计 {f.emergency_kwh.sum():,.2f} kWh',loc='left',fontsize=12,pad=8)
    ax.set(xlim=(0,24),xticks=range(0,25,2));ax.tick_params(direction='in')
    facts[date]={'intervals':len(f),'emergency_kwh':float(f.emergency_kwh.sum()),'state_points':145}
axes[-1].set_xlabel('时刻 / h')
handles=[Line2D([0],[0],color='#1f78b4',lw=1.8,label='实际储能（左轴）'),
    Line2D([0],[0],color='#7a828d',ls='--',label='日前计划（左轴）'),
    Patch(facecolor='#fdbf6f',label='每十分钟紧急购电（右轴）')]
fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.52,.948),ncol=3,fontsize=10)
fig.get_layout_engine().set(rect=(0,.07,1,.89))
fig.text(.075,.026,'四日使用相同纵轴尺度；灰色水平虚线为1.2与10.8 MWh边界。沿用内部时间假设，实际状态不按日重置。',fontsize=9.8,color='#59636f')
for ext in ['png','svg']:
    fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out/'plot_facts.json').write_text(json.dumps(facts,indent=2)+'\n')
