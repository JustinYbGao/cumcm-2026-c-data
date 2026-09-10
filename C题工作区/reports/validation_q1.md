# q1 数据验证

验证对象为重新读取的 CSV；任何未通过项均保留。

| 检查 | 结果 | 证据 |
|---|---|---|
| Q1: 144 slots unique and ordered | 通过 |  |
| Q1: complete relative day intervals | 通过 |  |
| Q1: required values nonmissing | 通过 |  |
| fixed_price: 144 slots unique and ordered | 通过 |  |
| fixed_price: complete relative day intervals | 通过 |  |
| fixed_price: required values nonmissing | 通过 |  |
| Q1: all original numeric cells preserved | 通过 |  |
| Q1: energy and signed net load | 通过 |  |
| Q1: fixed price identical | 通过 |  |
| Q1: negative net and zeros preserved | 通过 | negative net=30, PV zero=55 |
| All original workbooks including templates unchanged | 通过 |  |
