"""Small local table renderer; no optional tabulate dependency."""
import numbers
import pandas as pd


def markdown(frame):
    def cell(value):
        if pd.isna(value):return ''
        if isinstance(value,numbers.Real) and not isinstance(value,bool):return f'{value:.6f}'
        return str(value).replace('|','\\|').replace('\n',' ')
    lines=['| '+' | '.join(map(str,frame.columns))+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    lines += ['| '+' | '.join(cell(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None)]
    return '\n'.join(lines)
