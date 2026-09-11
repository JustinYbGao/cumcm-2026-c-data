"""Append missing initializer certificates; original January artifacts are retained."""
import json
from policy import WORK,ROOT,INPUTS,np,pd,decision,PLAN_KEYS,save_json

archive=pd.read_csv(ROOT/'forecasts/linear_harmonic.csv',float_precision='round_trip')
price=pd.read_csv(INPUTS/'fixed_price.csv',float_precision='round_trip').price_yuan_per_kwh.to_numpy()
for cfg in json.loads((WORK/'configs/q2_direct_v4/experiments.json').read_text())['runs']:
    folder=ROOT/'january'/cfg['policy'];days=json.loads((folder/'decisions.json').read_text())['days']
    old=np.load(folder/'decision_evidence.npz');plans=[]
    for i,day in enumerate(days):
        f=archive.loc[archive.date==day['date']]
        d=decision(archive,pd.Timestamp(day['date']),f.load_forecast_kwh.to_numpy(),f.pv_forecast_kwh.to_numpy(),price,day['initial_energy_kwh'],cfg)
        assert np.array_equal(old['q'][i],d['q'])
        assert np.array_equal(old['score'][i],d['score'])
        plans.append(d['initializer_plan'])
    np.savez_compressed(folder/'initializer_certificate.npz',initializer_plan=np.asarray(plans))
    save_json(folder/'initializer_certificate_note.json',{'scope':'Additional rerun certificate, original q and score bitwise identical for all six candidates on every January day. Original artifacts unchanged.','columns':PLAN_KEYS})
