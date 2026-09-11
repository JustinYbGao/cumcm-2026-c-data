"""Real monthly ablations in the TRD_004 line/bar visual grammar."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

path=Path(sys.argv[1]);out=Path(sys.argv[2]);out.mkdir(parents=True,exist_ok=True)
f=pd.read_csv(path);x=np.arange(len(f));months=pd.to_datetime(f.month).dt.strftime('%b')
plt.rcParams.update({'font.family':'DejaVu Serif','font.size':10,'axes.spines.top':False,'axes.spines.right':False,'svg.fonttype':'none'})
fig,axes=plt.subplots(3,1,figsize=(11,9),sharex=True);fig.subplots_adjust(left=.10,right=.88,top=.86,bottom=.12,hspace=.36)
blue='#3B6C8E';orange='#CB8B52';gray='#676D73'
pairs=[('pv_raw','pv_bias','A  |  PV bias correction'),('risk_none','risk_fixed','B  |  Fixed reserve (2400 kWh)'),('gate_paid','gate_q75','C  |  Reliability gate (alpha = 0.75)')]
for ax,(base,candidate,title) in zip(axes,pairs):
    saving=f[base]-f[candidate];other=ax.twinx();other.spines['top'].set_visible(False)
    ax.plot(x,f[base]/1e6,color=gray,lw=1.7,ls='--',marker='o',ms=3)
    ax.plot(x,f[candidate]/1e6,color=blue,lw=1.6,marker='o',ms=3)
    other.bar(x,saving,color=orange,alpha=.32,width=.56,zorder=0);other.axhline(0,color=orange,lw=.7,alpha=.6)
    scale=max(1.,float(np.abs(saving).max())*1.25);other.set_ylim(-scale,scale)
    ax.set_ylabel('Actual cost (million CNY)');other.set_ylabel('Savings (CNY)',color='#9C6337')
    ax.set_title(title,loc='left',fontsize=11,pad=7);ax.grid(axis='y',alpha=.16)
    ax.text(.99,1.045,f'Total savings: {saving.sum():,.2f} CNY',transform=ax.transAxes,ha='right',va='bottom',fontsize=9)
    ax.set_zorder(other.get_zorder()+1);ax.patch.set_visible(False)
axes[-1].set_xticks(x,months);axes[-1].set_xlabel('Evaluation month in 2025')
fig.suptitle('Innovation ablations: small gains and negative results',y=.96,fontsize=15)
fig.legend(handles=[Line2D([],[],color=gray,ls='--',label='Matched baseline'),Line2D([],[],color=blue,label='Candidate'),Patch(color=orange,alpha=.32,label='Baseline minus candidate')],loc='upper center',bbox_to_anchor=(.5,.918),ncol=3,frameon=False)
fig.text(.1,.046,'Same realized tariff within each panel. Positive bars indicate savings; each right axis has its own scale.',fontsize=8)
fig.text(.1,.027,'Predeclared ablations; panel C was not selected in March. Exploratory internal results, April–December.',fontsize=8)
fig.savefig(out/'chart.png',dpi=300);fig.savefig(out/'chart.svg');plt.close(fig)
