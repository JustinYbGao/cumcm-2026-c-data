"""Saved usage example; only prints causal slice sizes, no predictive features."""
import pandas as pd
from prepare_data import OUT, history_at, forecasts_at

if __name__=='__main__':
    actual = pd.read_csv(OUT/'actual_10min.csv')
    hourly = pd.read_csv(OUT/'pv_forecast_hourly.csv')
    derived = pd.read_csv(OUT/'pv_forecast_10min.csv')
    decision = '2025-02-01T00:00:00'
    print('Decision:',decision)
    print('Completed actual intervals:',len(history_at(actual,decision)))
    print('Available future hourly forecast versions:',len(forecasts_at(hourly,decision)))
    print('Available future 10-minute forecast versions:',len(forecasts_at(derived,decision)))
