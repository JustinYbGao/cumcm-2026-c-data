"""Adapt ModelViz 12_TRD_004 blue/orange/gray bar-line composition.
Separate the auxiliary difference axis into a shared-x panel; omit unrelated regression.
"""
import json
from pathlib import Path
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd

font_manager.fontManager.addfont('/System/Library/Fonts/Supplemental/Songti.ttc')
plt.rcParams.update({'font.family':['Times New Roman','Songti SC'],'font.size':11,
    'axes.unicode_minus':False,'axes.spines.top':False,'axes.spines.right':False,
    'axes.linewidth':.8,'axes.labelpad':8,'legend.frameon':False,
    'svg.hashsalt':'cumcm-modelviz-v2','savefig.facecolor':'white'})
d=pd.read_csv(sys.argv[1],float_precision='round_trip')
out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
assert len(d)==11 and d.month.tolist()==[f'2025-{i:02d}' for i in range(2,13)]
assert np.allclose(d.total_cost_yuan-d.seasonal_total_cost_yuan,d.excess_cost_yuan,atol=1e-6,rtol=0)
x=np.arange(len(d)); delta=d.excess_cost_yuan/10000
total=d.total_cost_yuan.sum()/10000
baseline=d.seasonal_total_cost_yuan.sum()/10000
fig,axes=plt.subplots(2,1,figsize=(10.5,7.7),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2.3,1]})
fig.suptitle('问题2  |  月度费用与季节基线比较',fontsize=17,y=.985,x=.075,ha='left')
axes[0].bar(x,d.planned_cost_yuan/10000,width=.58,color='#a6cee3',label='选中策略：计划购电费')
axes[0].bar(x,d.emergency_cost_yuan/10000,width=.58,bottom=d.planned_cost_yuan/10000,
    color='#fdbf6f',label='选中策略：紧急购电费')
axes[0].plot(x,d.seasonal_total_cost_yuan/10000,'o-',color='#555555',lw=1.7,ms=4,label='季节基线：总费用')
axes[0].set(ylabel='购电费用 / 万元',ylim=(0,245),yticks=[0,50,100,150,200])
axes[0].set_title('(a) 月度费用组成',loc='left',fontsize=12,pad=9)
axes[0].legend(ncol=3,loc='upper left',fontsize=9.7,columnspacing=1.3)
axes[0].text(.02,.83,f'2—12月合计：选中策略 {total:,.2f} 万元  |  季节基线 {baseline:,.2f} 万元',
    transform=axes[0].transAxes,fontsize=10,color='#3d4854')
axes[1].bar(x,delta,width=.58,color=np.where(delta>=0,'#cf7957','#4c9a8b'))
axes[1].axhline(0,color='#59636f',lw=.8)
for i,value in enumerate(delta):
    axes[1].text(i,value+(1.1 if value>=0 else -1.1),f'{value:+.2f}',ha='center',
        va='bottom' if value>=0 else 'top',fontsize=10,color='#785044' if value>=0 else '#34776b')
axes[1].set(ylabel='费用差 / 万元',xlabel='2025年月度',ylim=(-19,40),xticks=x,xticklabels=[f'{i}月' for i in range(2,13)])
axes[1].set_title(f'(b) 选中策略 − 季节基线：累计 +{total-baseline:.2f} 万元（+{(total/baseline-1)*100:.2f}%）',loc='left',fontsize=12,pad=9)
for ax in axes:
    ax.set_axisbelow(True);ax.grid(axis='y',color='#d5dbe0',lw=.5,alpha=.7)
    ax.tick_params(direction='in');ax.set_xlim(-.6,10.6)
fig.get_layout_engine().set(rect=(0,.07,1,.84))
fig.text(.075,.025,'选型仅使用1月历史；2—12月为冻结评价期。正差表示选中策略费用更高。内部工作假设，非正式提交版。',fontsize=9.8,color='#59636f')
for ext in ['png','svg']:
    fig.savefig(out/f'chart.{ext}',dpi=300,metadata={'Date':None} if ext=='svg' else None)
plt.close(fig)
(out.parent/'workspace/plot_facts.json').write_text(json.dumps({'months':len(d),'selected_cost_yuan':float(total*10000),
    'seasonal_cost_yuan':float(baseline*10000),'excess_cost_yuan':float(delta.sum()*10000)},indent=2)+'\n')
