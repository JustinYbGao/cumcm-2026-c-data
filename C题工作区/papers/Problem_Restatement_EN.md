# 1 Problem Restatement

## 1.1 Research Background

With distributed photovoltaic (PV) generation connected to residential communities, electricity demand, PV output, the state of energy storage, and the price of electricity exchanged with the external grid form a continuously changing supply–demand system. A grid-connected, non-islanded microgrid must reliably meet community demand while using storage to absorb energy during low-price or PV-surplus periods and release it when electricity is more expensive. This improves local PV utilization and helps control the cost of purchased electricity.

This problem concerns intraday power scheduling for a grid-connected microgrid. Its main challenge is the variability of PV output and load, the possible mismatch between forecasts and actual generation, and the limits imposed by storage capacity, charging/discharging power, efficiency, and safe energy bounds. Under fixed and time-varying tariffs, with or without plan revisions and associated settlement charges, a purchasing and storage-operation policy is required to balance supply reliability and economic performance.

## 1.2 Problem Review

The storage unit has a maximum capacity of 12,000 kWh, a maximum charging/discharging power of 5,000 kW, and a charging/discharging efficiency of 90%. Its stored energy must remain between 1,200 and 10,800 kWh, and its energy at 00:00 on January 1, 2025 is 6,000 kWh. The load and PV data are measured in kW, electricity prices in CNY/kWh, and reported purchased and charged/discharged electricity in kWh. In every task, the electricity supplied by the microgrid must not fall below the community load.

**Problem 1: Day-ahead scheduling with identical daily load and tariff.** Given a repeated daily tariff and load profile and the forecast PV power for one day, determine a planned electricity-purchasing policy at 00:00 each day, subject to equal storage energy at 00:00 and 24:00. Using Appendix 1 and Attachment 1, report purchases for the specified 10-minute intervals, total daily purchases and cost, charging and discharging over six four-hour intervals, and beginning and ending storage energy. Save the complete schedule in `result1.xlsx` following the provided template.

**Problem 2: Day-ahead scheduling with varying realized load and PV output.** The daily tariff remains unchanged, whereas the community load and actual PV generation vary over time. Based on the tariff in Attachment 1 and the 2025 time-series data in Attachment 2, prepare a planned purchase schedule at 00:00 every day. If supply is insufficient in actual operation, the deficit must be covered by emergency purchases charged at five times the tariff at that trading time; purchases in all other periods are charged according to the planned amount. Produce complete schedules from February 1 through December 31, 2025, present planned purchases, storage operation, and emergency purchases for March 20, June 21, September 23, and December 21, and complete `result2.xlsx`.

**Problem 3: Schedule revision using multiple PV forecasts.** At 00:00, 06:00, 12:00, and 18:00 each day, a 24-hour hourly PV forecast becomes available. A purchase plan is made from the 00:00 forecast and may be revised using later forecasts. For any reduction from the planned amount, a breach charge equal to 50% of the tariff at the trading time applies; for any amount added above the plan, the excess is priced at 1.5 times that tariff. Total cost includes planned-purchase cost, emergency-purchase cost, and revision-related charges. Using Attachments 1–3, develop the annual schedules, report the required results for the specified dates, complete `result3.xlsx`, and assess whether subsequent forecasts should be used to revise the plan.

**Problem 4: Rescheduling under time-varying tariffs.** Replace the fixed tariff with the 2025 real-time price data in Attachment 4. Using actual load and PV data from Attachment 2 and PV forecasts from Attachment 3, recompute the results for Problems 2 and 3, report the corresponding results, and save the complete schedules as `result4-2.xlsx` and `result4-3.xlsx`, respectively.

## 1.3 Literature Review

Microgrid research commonly treats distributed generation, energy storage, and loads as a locally coordinated energy system. Lasseter introduced the MicroGrid concept as a controllable aggregation of loads and microsources that can interact with the utility system [1]. Guerrero et al. later discussed hierarchical microgrid control, including management of power flow between a microgrid and the external distribution grid [2]. For grid-connected microgrids, day-ahead energy management is often formulated to minimize purchased-electricity cost or total operating cost while enforcing power balance, battery state-of-charge limits, charging/discharging limits, and equipment operating constraints. Tenfen and Finardi formulated microgrid energy management as a mixed-integer linear programming problem, illustrating the suitability of this approach when discrete operating states coexist with linear technical constraints [3]. Sigalo et al. applied a related formulation to battery control in a grid-connected microgrid [4].

Forecast errors in load, PV generation, and electricity prices can make a deterministic day-ahead schedule inconsistent with realized operation. To respond to such uncertainty, the literature employs stochastic programming, robust optimization, and receding-horizon control to update dispatch decisions as new information becomes available. In an experimental study, Parisio, Rikos, and Glielmo combined two-stage stochastic programming with model predictive control to address uncertainty in renewable generation and demand [5]. These approaches can reconcile advance planning with operational adaptation, but they require a defensible description of forecast error, clear information-availability times, and sufficient computation within each decision interval. Existing studies often emphasize device-level control or general multi-resource scheduling; they do not necessarily represent a settlement framework that simultaneously includes planned purchases, schedule revisions, emergency purchases, and asymmetric revision charges. This problem therefore provides a setting to compare fixed and variable price scenarios while accounting consistently for storage constraints, forecast-update timing, and the cost consequences of plan revisions.

### Verified References

[1] Lasseter, R. H. *MicroGrids*. 2002 IEEE Power Engineering Society Winter Meeting, 2002. DOI: [10.1109/PESW.2002.985003](https://doi.org/10.1109/PESW.2002.985003).

[2] Guerrero, J. M., Vasquez, J. C., Matas, J., de Vicuña, L. G., & Castilla, M. Hierarchical Control of Droop-Controlled AC and DC Microgrids—A General Approach Toward Standardization. *IEEE Transactions on Industrial Electronics*, 58(1), 158–172, 2011. DOI: [10.1109/TIE.2010.2066534](https://doi.org/10.1109/TIE.2010.2066534).

[3] Tenfen, D., & Finardi, E. C. A mixed integer linear programming model for the energy management problem of microgrids. *Electric Power Systems Research*, 122, 19–28, 2015. DOI: [10.1016/j.epsr.2014.12.019](https://doi.org/10.1016/j.epsr.2014.12.019).

[4] Sigalo, M. B., Pillai, A. C., Das, S., & Abusara, M. An Energy Management System for the Control of Battery Storage in a Grid-Connected Microgrid Using Mixed Integer Linear Programming. *Energies*, 14(19), 6212, 2021. DOI: [10.3390/en14196212](https://doi.org/10.3390/en14196212).

[5] Parisio, A., Rikos, E., & Glielmo, L. Stochastic model predictive control for economic/environmental operation management of microgrids: An experimental case study. *Journal of Process Control*, 43, 24–37, 2016. DOI: [10.1016/j.jprocont.2016.04.008](https://doi.org/10.1016/j.jprocont.2016.04.008).

## Items Requiring Confirmation

1. The statement specifies a 6,000 kWh initial storage level only at 00:00 on January 1, 2025. The daily initial energy in Problem 1 and whether storage energy should carry over continuously between days in Problems 2–4 should be stated explicitly as modeling assumptions.
2. The statement does not specify whether “90% charging/discharging efficiency” means 90% efficiency in each direction or 90% round-trip efficiency. A consistent interpretation, with an appropriate sensitivity discussion, is needed.
3. Before submission, verify the time alignment between the 10-minute power records and hourly PV forecasts, forecast coverage, and the time-row mapping in the Attachment 5 templates.

# 2 Problem Analysis

The four tasks form a sequential energy-management problem that combines time-series forecasting, constrained scheduling, online plan revision, and ex-post cost accounting. Their common physical core is the power balance between community load, PV generation, grid purchases, and battery charging or discharging, subject to storage capacity, power, efficiency, and state-of-charge limits. Problem 1 is a deterministic day-ahead scheduling problem because its tariff, load, and PV forecast are supplied as fixed inputs. Problem 2 introduces forecast-to-realization deviation and an asymmetric penalty for unmet demand, so it requires both a day-ahead planning layer and a causal execution layer. Problem 3 retains the same physical system but expands the information set at 06:00, 12:00, and 18:00; it is therefore a multi-stage scheduling problem with revision costs. Problem 4 preserves the two mechanisms of Problems 2 and 3 while replacing the fixed tariff with a time-varying price process. A single scheduling architecture can consequently be used throughout, while the available information, settlement rule, and tariff input are changed in a controlled manner.

The linkage between the tasks is essential. The storage-state convention, unit conversion, power-balance logic, and feasibility audit established for Problem 1 become the common foundation for the remaining tasks. Problem 2 adds forecasts of the uncertain load and PV output, a record of realized operation, emergency purchases, and a continuously updated battery state. These records become the temporal interface for Problem 3, where only the unexecuted part of the schedule may be reconsidered after a new PV forecast is released. Problem 4 should retain two separate strategy branches: one corresponding to the day-ahead mechanism of Problem 2 and the other to the revision mechanism of Problem 3. Each branch must maintain its own continuous state-of-charge trajectory; a state generated by one strategy cannot be reused by another. This design makes comparisons attributable to the intended changes in information or price conditions rather than to inconsistent storage initialization or execution rules.

The input data have heterogeneous time resolutions and must be organized before any optimization. Attachment 1 provides one daily profile with 144 ten-minute observations of tariff, load, and PV forecast. Attachments 2 and 4 provide 365 daily profiles, yielding 52,560 ten-minute observations each after time indexing. Attachment 3 contains four forecast releases per day and 24 hourly targets per release, for 35,040 forecast-version/target records over 2025. Load and PV are power measurements in kW, whereas purchases, battery flows, and the final outputs are energy quantities in kWh; the tariff is measured in CNY/kWh. The ten-minute power records can be converted to interval energy under an explicitly stated interval-average-power convention. The hourly PV forecasts require a separate, documented conversion to the ten-minute optimization grid. Because the statement identifies them as hourly point forecasts rather than interval averages, the interpolation and endpoint treatment are processing assumptions rather than facts of the problem and must be fixed before model comparison.

The current data audit should be used as a quality-control baseline, not as a source of unverified operational conclusions. It reports no missing, non-numeric, or non-finite values in the numerical input regions and no negative load, PV, or price values. Valid zero observations, including zero PV output, are retained rather than replaced. Attachment 3 contains blank date labels in repeated rows; these are structural labels that can be filled downward while preserving the original row order and a transformation log, rather than being treated as missing PV forecasts. Large adjacent changes should be flagged for source-cell review but not automatically deleted or smoothed, since a jump alone does not prove a measurement error. The review should also confirm uniqueness of the date–time key, the one-to-one correspondence among the load, PV, and price time grids, and the source-to-template mapping. Lagged and seasonal dependence may be examined on chronologically available history to guide forecasting, but it should not be presented as causal evidence or be allowed to leak future observations into an earlier decision.

For Problem 1, the supplied load, PV forecast, and fixed tariff permit a deterministic economic-dispatch formulation. The decision layer determines regular grid purchases and battery charging or discharging jointly across the day, rather than optimizing each interval independently, because a battery action changes the feasible energy available later. A linear programming baseline is appropriate for checking the energy-accounting structure. If simultaneous charging and discharging must be explicitly excluded, a mixed-integer linear formulation is the more direct option; the choice should be justified by the final constraint representation rather than by algorithmic complexity. The solution will be checked by independently recomputing interval energy balance, storage transitions, power limits, storage bounds, the required equality of beginning and ending energy, and the reported purchase cost from the exported schedule.

Problem 2 extends this baseline from a known day to a rolling sequence of uncertain days. The day-ahead plan should use only information available at 00:00, with interpretable time-series baselines for load and PV constructed from past observations, calendar position, and periodic structure where supported by chronological validation. More flexible alternatives, such as generalized additive or risk-quantile models, should be retained only if they improve an out-of-sample decision criterion under the same information boundary. After the plan is set, realized load and PV must be passed through one explicit execution rule that updates the battery state interval by interval and uses emergency purchases solely to cover an actual shortfall. This separation prevents future realizations from being used to create the original plan and ensures that the fivefold emergency price is evaluated as a real consequence of forecast and operating errors. A possible extension is to reserve a data-supported energy margin for consecutive net-load errors, but it should remain a tested alternative rather than an assumed guarantee.

For Problem 3, Attachment 3 should first be used in its original release structure, with any forecast-bias correction treated as an optional, separately validated component. At each permitted update time, the current state of charge, already executed decisions, current purchase commitment, and the newest admissible forecast define the new decision state. A receding-horizon or model-predictive-control framework is suitable because it freezes executed intervals and re-optimizes only future intervals. The model must be able to retain the existing commitment when revision is not economically justified; otherwise, it cannot distinguish the value of better information from the cost of changing a purchase plan. The exact accounting treatment for reductions in planned purchases is not fully specified by the statement—especially whether cancelled energy is refunded and whether repeated changes are charged transaction by transaction. The chosen interpretation must therefore be stated, applied once per commitment, and, if no official clarification is available, tested as clearly labeled alternative settlement scenarios rather than silently assumed.

Problem 4 is a price-information extension rather than an entirely new physical system. The Problem 2 branch is rerun with time-varying prices in the day-ahead objective and actual settlement, while the Problem 3 branch combines the same prices with forecast updates and paid revisions. The statement supplies realized prices but does not explicitly say whether future intraday prices are known when a decision is made. If they are unavailable, a price forecast using only prior information is required; if perfect future-price knowledge is adopted, it must be declared as a separate information scenario. The two branches should share the same data conventions, execution logic, and validation protocol while preserving distinct storage paths. Throughout Problems 2–4, time-ordered backtesting, not random row splitting, is needed to evaluate forecasting components. Final verification should include an independent re-read of each result workbook, consistency of all costs with the selected settlement rule, feasibility of every ten-minute interval, cross-day state continuity, and completeness of the required output sheets.

## Overall Solution Framework Design

- Attachment 1, Attachment 2, Attachment 3, Attachment 4, storage parameters, and Attachment 5 templates → source inventory and time/unit audit.
- Source inventory and time/unit audit → key validation, missing-label handling, valid-zero preservation, and anomaly flagging → decision-ready fixed-price, realized-operation, forecast-version, and variable-price data sets.
- Decision-ready data sets → information-availability filter at each decision time → admissible historical observations, current storage state, and available forecasts/prices.
- Fixed inputs from Attachment 1 → deterministic storage-constrained day-ahead schedule for Problem 1 → physical and cost audit → `result1.xlsx`.
- Chronologically available history → load/PV forecasting baseline and optional risk-margin candidates → Problem 2 day-ahead schedule → causal realized-operation replay with emergency purchases → feasibility and settlement audit → `result2.xlsx`.
- Problem 2 execution state and Attachment 3 forecast versions → 00:00 plan → 06:00/12:00/18:00 update decisions for unexecuted intervals → final commitment, realized-operation replay, and revision-cost audit → `result3.xlsx`.
- Variable-price data and declared price-information scenario → Problem 2 mechanism under variable prices → independent replay and audit → `result4-2.xlsx`.
- Variable-price data and declared price-information scenario → Problem 3 revision mechanism under variable prices → independent replay and audit → `result4-3.xlsx`.
- All four audited strategy records → constraint checks, chronological-validation checks, template-completeness checks, and comparable cost-accounting review → tables and discussion for the paper.

## Items Requiring Confirmation

1. Whether a ten-minute timestamp denotes the beginning or end of its interval, and how the time rows in Attachment 5 map to the source data.
2. Whether the stated 90% efficiency applies separately to charging and discharging or to the round trip, and whether the 5,000 kW limit is measured on the grid/bus side or battery side.
3. Whether storage state is required to carry continuously from one day to the next in Problems 2–4, and what terminal condition is intended for those problems.
4. Whether future variable prices in Problem 4 are known at the decision time; otherwise, the permitted price-forecast information set must be defined.
5. Whether a reduction from the original purchase plan receives a refund, and whether a later revision is settled only against the original plan or against every preceding revision.
6. Whether hourly PV forecast values represent instantaneous point values or hourly averages, including the endpoint rule needed to convert them to ten-minute energy.

# 3 Model Assumptions

To emphasize the central characteristics of microgrid scheduling and reduce the influence of factors that are not specified in the statement, the following assumptions are made on the basis of three sources: conditions explicitly supplied by the problem, operating conditions reasonably inferred from those conditions, and additional conditions required to make the scheduling model executable and auditable. They do not assert that the data, forecasting models, or resulting schedules are intrinsically correct.

1. **Assumption 1: The retained, time-aligned load, PV, forecast, and tariff observations represent the corresponding operating intervals and are suitable as model inputs.**  
   **Explanation:** This is a data-use condition rather than a claim that every measurement is error-free. After structural label handling, key checks, and source tracing, the retained data are used without automatically deleting valid zero values or abrupt changes. This preserves the observed supply–demand variation for forecasting and replay while allowing flagged source values to remain subject to later review.

2. **Assumption 2: Each ten-minute load or PV power record is the interval-average power, and hourly PV forecasts can be converted to ten-minute energy through a fixed interpolation convention.**  
   **Explanation:** The optimization requires a common energy unit, whereas the supplied actual series are ten-minute kW records and the PV forecasts are hourly values. This assumption permits consistent conversion to kWh and preserves the forecast issue-time structure; it does not use future realized PV values to fill forecast endpoints. The timestamp orientation and the interpolation rule must be kept identical in planning, execution, and validation.

3. **Assumption 3: The battery is represented by a single aggregated energy state with the stated capacity, operating range, and charging/discharging power limits; self-discharge, degradation, ramping, and sub-interval converter dynamics are neglected.**  
   **Explanation:** The statement provides storage capacity, a safe SOC interval, a power limit, and efficiency, but no parameters for ageing or high-frequency dynamics. The simplification retains the intertemporal role of storage that is central to all four questions, while avoiding unsupported device-level parameters. Charging and discharging are mutually exclusive within a modeled interval.

4. **Assumption 4: The base case interprets the stated 90% efficiency as a one-way charging efficiency and a one-way discharging efficiency; the symmetric 90% round-trip interpretation is retained as a sensitivity case.**  
   **Explanation:** The wording of the statement does not identify whether 90% applies in each direction or to the full cycle. A single primary convention is needed to update SOC, but the alternative is evaluated separately because the choice changes feasible energy transfer and purchase cost. Neither convention is treated as an official interpretation before clarification.

5. **Assumption 5: Surplus electricity has no sale revenue; PV surplus may be curtailed, while any disposal of committed grid energy is permitted only in the Q2–Q4 execution and settlement branches that explicitly require it.**  
   **Explanation:** The problem specifies purchases and storage operation but supplies neither an export tariff nor a rule for selling back to the external grid. This condition prevents unsupported revenue through arbitrage. In particular, the Problem 1 model restricts surplus disposal to available PV, whereas the later no-refund or fixed-commitment branches may need a documented disposal channel for energy that has already been contracted. Emergency purchases are used only to cover an actual supply shortfall and never to charge the battery for arbitrage.

6. **Assumption 6: At every decision time, the schedule uses only completed actual observations, forecasts already released by that time, the current actual SOC, and price information permitted by the chosen scenario; actual SOC is propagated continuously across days.**  
   **Explanation:** This is required to distinguish a day-ahead or rolling decision from a retrospective schedule that uses future realizations. It connects the original commitment in Problem 2 to the forecast updates in Problem 3 and prevents state resets from artificially improving a later policy. No normality, independence, or stationarity assumption is imposed on forecast errors; forecasting components are assessed chronologically instead of by random row splitting.

7. **Assumption 7: For Problems 2–4, the planning model uses the current daily initial SOC as a terminal reference, while realized operation carries the actual terminal SOC into the next day; Problem 3 is settled once against the original 00:00 commitment under the declared settlement scenario.**  
   **Explanation:** The daily equality condition is explicit only in Problem 1, so its extension to later planning problems is a baseline modeling choice rather than a stated fact. Similarly, the wording of the reduction charge does not settle refund treatment or whether every intermediate revision is separately charged. The primary analysis uses the one-time refund-and-breach-charge scenario and keeps the no-refund alternative as a sensitivity branch, preventing either settlement interpretation from being silently imposed.

## Items Requiring Confirmation

- Confirm whether the source time labels denote interval starts or ends and reconcile them with the time rows in Attachment 5.
- Confirm whether the 90% efficiency is one-way or round-trip and whether the 5,000 kW limit is measured on the bus side or battery side.
- Confirm the intended terminal-SOC treatment for Problems 2–4 and whether actual storage must be continuous across days.
- Confirm whether future variable prices are known at the decision time and whether cancelled planned purchases are refunded or each revision is separately settled.
- Verify that the selected hourly-forecast interpolation convention is accepted for the official result templates.

# 4 Definitions and Notation

For clarity in the shared scheduling formulation, the principal symbols used repeatedly throughout the paper are summarized in Table 1. Local variables introduced for a single derivation are defined where they first appear.

**Table 1. Main notation**

| Symbol | Meaning | Unit |
|---|---|---|
| \(d\) | Index of an operating day in the evaluation horizon | — |
| \(t\) | Index of a ten-minute interval within day \(d\) | — |
| \(k\) | Index of a permitted decision/update time; \(k\in\{00{:}00,06{:}00,12{:}00,18{:}00\}\) when PV updates are available | — |
| \(T\) | Number of ten-minute intervals in one day, equal to 144 | — |
| \(\Delta t\) | Duration of one scheduling interval | h |
| \(\ell_{d,t}\) | Actual community load energy in interval \(t\) of day \(d\) | kWh |
| \(g_{d,t}\) | Actual PV generation energy in interval \(t\) of day \(d\) | kWh |
| \(\widehat{\ell}_{d,t\mid k}\) | Load-energy forecast for interval \(t\) of day \(d\), available at decision time \(k\) | kWh |
| \(\widehat{g}_{d,t\mid k}\) | PV-energy forecast for interval \(t\) of day \(d\), available at decision time \(k\) | kWh |
| \(p_{d,t}\) | Actual external-grid electricity price in interval \(t\) of day \(d\) | CNY/kWh |
| \(\widehat{p}_{d,t\mid k}\) | Electricity-price forecast for interval \(t\) of day \(d\), available at decision time \(k\) | CNY/kWh |
| \(q^0_{d,t}\) | Original regular grid-purchase commitment made at 00:00 for interval \(t\) of day \(d\) | kWh |
| \(q^k_{d,t}\) | Regular grid-purchase commitment for interval \(t\) of day \(d\) after the update at time \(k\) | kWh |
| \(\bar q_{d,t}\) | Final regular grid-purchase commitment executed in interval \(t\) of day \(d\) | kWh |
| \(e_{d,t}\) | Emergency grid purchase used to cover an actual deficit in interval \(t\) of day \(d\) | kWh |
| \(c_{d,t}\) | Energy charged from the microgrid bus into the battery in interval \(t\) of day \(d\) | kWh |
| \(b_{d,t}\) | Energy discharged from the battery to the microgrid bus in interval \(t\) of day \(d\) | kWh |
| \(E_{d,t}\) | Battery stored energy at the beginning of interval \(t\) of day \(d\) | kWh |
| \(w_{d,t}\) | Non-revenue surplus energy disposed of in interval \(t\) of day \(d\) | kWh |
| \(z_{d,t}\) | Binary charging/discharging mode for interval \(t\) of day \(d\) | — |
| \(\eta_c,\eta_d\) | Charging and discharging efficiencies, respectively | — |
| \(\mathcal{K}\) | Set of permitted PV-forecast update times | — |
| \(\mathcal{H}_k\) | Set of intervals not yet executed at decision time \(k\) | — |
| \(J\) | Realized electricity cost under a specified policy and settlement scenario | CNY |

*Note: Local symbols not listed in the table are explained where they first appear in the text.*

## Items Requiring Confirmation

- \(c_{d,t}\) and \(b_{d,t}\) are currently defined on the microgrid-bus side. This must be retained or both definitions and efficiency equations must be changed if the 5,000 kW limit is confirmed to apply on the battery side.
- \(\widehat p_{d,t\mid k}\) is used only in the causal-price scenario. In the perfect-price benchmark, it is replaced by the corresponding realized price by design.
- The final rule for \(q^k_{d,t}\) settlement remains pending: the current manuscript reports final-commitment, one-time settlement against \(q^0_{d,t}\), not a confirmed transaction-by-transaction market rule.

# 5 Model Establishment and Solution

## 5.1 Common Data Processing and Cross-Problem Interfaces

The four questions share the battery parameters, the 10-minute time grid, and the physical energy-balance structure. Attachment 1 supplies one 144-interval daily profile of fixed tariff, load, and PV forecast. Attachment 2 and Attachment 4 each provide 365 daily profiles, or 52,560 ten-minute records after time indexing. Attachment 3 provides four forecast releases per day, each with 24 hourly targets, for 35,040 forecast-version/target records. The numerical series are converted to energy consistently in kWh, forecast versions are retained by their release time, and all data joins are checked on explicit date-time keys. Valid zero PV observations and abrupt but traceable changes are retained; structural blank date labels in the forecast sheet are handled as repeated labels rather than imputed PV values.

The physical outputs of every question use the same symbols and units defined in Chapter 4. Problem 1 establishes the deterministic battery-dispatch core. Problem 2 adds causal forecasts, a fixed day-ahead commitment, and a realized-operation replay. Problem 3 inherits the same actual SOC and execution rules but allows forecast-driven revisions at the prescribed times. Problem 4 retains the two branches of Problems 2 and 3 while replacing the fixed planning price by a causally forecast price. Thus, no policy is allowed to borrow a terminal SOC, a future forecast, or a price realization from another strategy.

## 5.2 Problem 1: Model Establishment and Solution

### 5.2.1 Modeling Rationale and Model Selection

Problem 1 seeks a least-cost day-ahead purchase and battery schedule under known daily load, PV forecast, and tariff profiles. It is a deterministic finite-horizon economic-dispatch problem with intertemporal storage constraints. A mixed-integer linear program is selected because energy balance, storage evolution, capacity limits, power limits, and purchase cost are linear under the declared efficiency convention, whereas simultaneous charging and discharging must be excluded. A linear-programming relaxation is retained as a lower-bound and structural cross-check.

### 5.2.2 Data Processing

This problem uses the 144 ten-minute records in Attachment 1 and the battery parameters in Appendix 1. Load and PV power are converted to interval energy by multiplying by \(\Delta t=1/6\) h; the tariff already has units of CNY/kWh and is not scaled. The processed input therefore contains 144 valid scheduling intervals with fixed price, load energy, and forecast PV energy. No independent demand or PV forecasting model is introduced because the required forecast is supplied directly by the attachment.

### 5.2.3 Model Formulation

Let regular purchase \(q_t\), charge \(c_t\), discharge \(b_t\), surplus disposal \(w_t\), stored energy \(E_t\), and operating-mode variable \(z_t\) be the decision variables. The model minimizes the daily regular-purchase bill:

$$
\min J_1=\sum_{t=1}^{T}p_tq_t.
$$

The complete formulation is

$$
\begin{aligned}
q_t+\widehat g_t+b_t&=\widehat\ell_t+c_t+w_t, &&t=1,\ldots,T,\\
E_{t+1}&=E_t+\eta_cc_t-\frac{b_t}{\eta_d}, &&t=1,\ldots,T,\\
1200\le E_t&\le10800, &&t=1,\ldots,T+1,\\
0\le c_t&\le\frac{5000}{6}z_t,\qquad
0\le b_t\le\frac{5000}{6}(1-z_t), &&t=1,\ldots,T,\\
q_t,w_t&\ge0,\qquad z_t\in\{0,1\}, &&t=1,\ldots,T,\\
0\le w_t&\le\widehat g_t, &&t=1,\ldots,T,\\
E_1&=E_{T+1}=6000.
\end{aligned}
$$

The first constraint enforces interval energy balance, the second updates battery energy, the next two impose safe operating and power limits, and the final equality implements the explicit same-SOC requirement of Problem 1.

### 5.2.4 Model Solution

The MILP is solved with HiGHS 1.14.0 under Python 3.12.14. The implementation uses one thread, random seed 0, a 120-second time limit, relative and absolute MIP-gap tolerances of \(10^{-9}\) and \(10^{-7}\) CNY, and primal, dual, and integer feasibility tolerances of \(10^{-8}\). No separate maximum-iteration limit is specified; termination is controlled by the solver status, gap tolerances, or time limit. The reproducible source is maintained in the project solver script, but the formal supplementary-code number has not yet been assigned.

### 5.2.5 Results Analysis

The optimized plan purchases 59,482.698998 kWh and incurs a modeled cost of CNY 35,126.948589. At the six required ten-minute intervals, purchases are 0.000000, 480.412450, 0.000000, 445.431650, 531.894050, and 0.000000 kWh from 10:00 through 20:10 in the order specified by the statement. The SOC starts and ends at 6,000 kWh, while the four-hour charge/discharge totals are reported in Tables 2 and 3. Compared with the no-storage policy under the same surplus-disposal convention, the modeled cost is lower by CNY 12,925.098002. The result is consistent with shifting usable energy across time, but this monetary reduction is not interpreted as a direct reduction in electricity demand.

**Table 2. Required purchase summary for Problem 1**

| Interval | Purchase (kWh) | Interval | Purchase (kWh) | Interval | Purchase (kWh) |
|---|---:|---|---:|---|---:|
| 10:00–10:10 | 0.000000 | 12:00–12:10 | 480.412450 | 14:00–14:10 | 0.000000 |
| 16:00–16:10 | 445.431650 | 18:00–18:10 | 531.894050 | 20:00–20:10 | 0.000000 |
| Daily total | 59,482.698998 | Daily cost (CNY) | 35,126.948589 | | |

**Table 3. Required storage summary for Problem 1**

| Interval | Charge (kWh) | Discharge (kWh) | Interval | Charge (kWh) | Discharge (kWh) |
|---|---:|---:|---|---:|---:|
| 00:00–04:00 | 4,500.000000 | 0.000000 | 04:00–08:00 | 833.333333 | 6,365.841200 |
| 08:00–12:00 | 4,787.964288 | 1,702.996983 | 12:00–16:00 | 5,286.035177 | 91.101383 |
| 16:00–20:00 | 0.000000 | 5,780.131883 | 20:00–24:00 | 5,333.333333 | 2,859.868117 |
| SOC at 00:00 | 6,000.000000 | | SOC at 24:00 | 6,000.000000 | |

### 5.2.6 Model Verification and Sensitivity Analysis

An independent read-back check recomputes interval energy balance, SOC recursion, capacity and power limits, non-negativity, charge/discharge exclusivity, the initial/terminal equality, and total cost. The maximum balance and SOC-recursion residuals are \(1.14\times10^{-13}\) and \(8.81\times10^{-13}\) kWh, both below the \(10^{-6}\) kWh acceptance tolerance. The MILP objective equals the LP lower bound for this input, which supports optimality only for the stated deterministic formulation. Sensitivity to the two defensible interpretations of 90% efficiency changes the modeled cost to CNY 33,801.495542 under the symmetric round-trip convention; the conclusion is therefore conditional on the selected efficiency definition.

## 5.3 Problem 2: Model Establishment and Solution

### 5.3.1 Modeling Rationale and Model Selection

Problem 2 requires a daily commitment before uncertain load and PV outcomes are realized, followed by emergency purchases for actual deficits. It is a causal forecasting plus two-stage operational scheduling problem, rather than the deterministic dispatch in Problem 1. Interpretable seasonal, linear, and harmonic forecasting candidates are used because the available information is a dense, single-microgrid time series with calendar and lagged structure. The selected forecasts feed the same MILP battery model; a separate causal executor then produces actual SOC and emergency purchases without revising the original commitment.

### 5.3.2 Data Processing

Attachment 2 provides the actual load and PV records. January is used for warm-up and January 15–31 for a shadow comparison of forecasting candidates; the formal replay covers February 1–December 31, or 334 days and 48,096 ten-minute intervals. At each midnight, the load model uses only calendar features and completed lagged load values, while the PV candidates use only completed PV history. A 28-day load-training window with at least seven usable days, a seven-day PV-training window, two load harmonics, three PV harmonics, and a bounded first-order residual adjustment are used. No row is randomly split across time, and future actual night-time zero PV values are not used as forecast inputs.

### 5.3.3 Model Formulation

For day \(d\), the forecast layer produces \(\widehat\ell_{d,t\mid0}\) and \(\widehat g_{d,t\mid0}\). The day-ahead model minimizes planned fixed-tariff purchases,

$$
\widehat\ell_{d,t\mid0}=\left[\beta_0+\beta_1\ell_{d-1,t}/1000+\beta_2\ell_{d-7,t}/1000+
\sum_{j=1}^{6}\gamma_jI\{\mathrm{weekday}(d)=j\}+
\sum_{m=1}^{2}\left(a_m\sin\frac{2\pi mt}{144}+b_m\cos\frac{2\pi mt}{144}\right)\right]_+,
$$

$$
\widehat g_{u_0+h}=\left[f(t_h)^\top\alpha+\phi^h v_{u_0}\right]_+,
\qquad -0.99\le\phi\le0.99,
$$

where \(\beta_0,\beta_1,\beta_2,\gamma_j,a_m,b_m\) are load-regression coefficients, \(I\{\cdot\}\) is an indicator, \(f(\cdot)\) is the PV harmonic basis, \(\alpha\) is its coefficient vector, and \(v_{u_0}\) is the most recent PV residual. The first expression is the load forecast and the second is the harmonic PV forecast with a bounded first-order residual adjustment. The day-ahead model then minimizes planned fixed-tariff purchases,

$$
\min J^{\mathrm{plan}}_{2,d}=\sum_{t=1}^{T}p_tq^0_{d,t},
$$

subject to

$$
\begin{aligned}
q^0_{d,t}+\widehat g_{d,t\mid0}+b_{d,t}&=\widehat\ell_{d,t\mid0}+c_{d,t}+w_{d,t},\\
E_{d,t+1}&=E_{d,t}+\eta_cc_{d,t}-b_{d,t}/\eta_d,\\
1200\le E_{d,t}&\le10800,\\
0\le c_{d,t}&\le(5000/6)z_{d,t},\quad0\le b_{d,t}\le(5000/6)(1-z_{d,t}),\\
q^0_{d,t},w_{d,t}&\ge0,\quad z_{d,t}\in\{0,1\},\quad E_{d,T+1}=E_{d,1}.
\end{aligned}
$$

The final equality is a planning baseline; realized SOC is not reset. With regular commitment fixed, realized operation charges surplus first, discharges storage to meet an actual deficit, and makes an emergency purchase only for the residual deficit. The realized bill is

$$
J_2=\sum_{d,t}p_tq^0_{d,t}+5\sum_{d,t}p_te_{d,t}.
$$

Thus, unused committed energy remains charged, while emergency energy is explicitly penalized at five times the fixed tariff.

### 5.3.4 Model Solution

The system is run sequentially by day. January 1 uses a zero day-ahead commitment because no earlier history exists; January 2 onward uses the seasonal baseline for warm-up. The January candidate comparison freezes the linear-load/harmonic-PV structure on February 1, after which its parameters are re-estimated only from available past observations. Each daily MILP uses the same HiGHS environment, one thread, seed 0, 120-second time limit, and feasibility/gap tolerances as Problem 1. The model has no separately specified maximum iteration count. Forecast, plan, realized-operation, and ledger outputs are stored separately so that the original plan cannot be overwritten by actual execution.

### 5.3.5 Results Analysis

The January-selected linear/harmonic combination produces a February–December realized cost of CNY 16,333,683.39. The matched seasonal baseline costs CNY 15,378,207.35, and the matched no-storage policy costs CNY 20,022,731.00. Although the selected combination lowers planned-purchase expense, it produces CNY 1,231,302.05 more emergency expense than the seasonal baseline and therefore costs CNY 955,476.04 more overall. This result is deliberately retained as a negative control: a short calibration decision is not treated as evidence of annual economic superiority.

**Table 4. Problem 2 policy comparison over 334 days**

| Policy | Planned cost (CNY) | Emergency cost (CNY) | Realized cost (CNY) | Emergency purchase (kWh) |
|---|---:|---:|---:|---:|
| January-selected linear/harmonic policy | 11,987,831.57 | 4,345,851.83 | 16,333,683.39 | 751,884.12 |
| Seasonal baseline | 12,263,657.58 | 3,114,549.77 | 15,378,207.35 | 519,849.59 |
| No-storage baseline | 16,187,983.20 | 3,834,747.80 | 20,022,731.00 | 955,491.75 |

### 5.3.6 Model Verification and Sensitivity Analysis

An independent validator reconstructs the source series, forecast cutoff, planned balance, realized balance, SOC state, cross-day continuity, fixed-price billing, fivefold emergency billing, and representative-date tables without importing the solver or executor. It records 6,975 passing checks; the selected-policy maximum actual and planned balance residuals are approximately \(2.84\times10^{-13}\) and \(2.27\times10^{-12}\) kWh. A fixed reserve margin and an experimental risk-based margin yield only CNY 2–5 savings in their evaluated extension, so neither is claimed as an effective improvement. Full annual efficiency and terminal-condition sensitivity studies for Problem 2 have not been completed and remain outside the result claim.

## 5.4 Problem 3: Model Establishment and Solution

### 5.4.1 Modeling Rationale and Model Selection

Problem 3 adds released PV forecasts and paid purchase revisions at 06:00, 12:00, and 18:00. It is a multi-stage rolling scheduling problem with state feedback and piecewise-linear contract cost. Model predictive control is selected because each permitted update observes the actual SOC, freezes executed intervals, and re-optimizes only the remaining same-day horizon. The internal optimization remains a MILP so that the shared battery constraints and charge/discharge exclusivity are preserved.

### 5.4.2 Data Processing

The problem uses Attachment 1 for fixed tariffs, Attachment 2 for actual load/PV during execution, and Attachment 3 for release-specific PV forecasts. The evaluation horizon again contains 334 days and 48,096 ten-minute intervals. Each released hourly forecast is transformed to the ten-minute grid by the fixed interpolation convention and truncated at the current day's 24:00 boundary. The load-model structure selected in Problem 2 is retained and is re-estimated at midnight from past information only; it is not replaced after the annual Q2 comparison. All policies share the February 1 SOC from the January warm-up and then evolve independently.

### 5.4.3 Model Formulation

At 00:00, the original plan minimizes \(\sum_tp_tq^0_{d,t}\). At a permitted update time \(k\), the remaining-horizon balance and battery constraints are

$$
\begin{aligned}
q^k_{d,t}+\widehat g_{d,t\mid k}+b_{d,t}&=\widehat\ell_{d,t\mid0}+c_{d,t}+w_{d,t}, &&t\in\mathcal H_k,\\
E_{d,t+1}&=E_{d,t}+\eta_cc_{d,t}-b_{d,t}/\eta_d, &&t\in\mathcal H_k,\\
1200\le E_{d,t}&\le10800,\\
0\le c_{d,t}&\le(5000/6)z_{d,t},\quad0\le b_{d,t}\le(5000/6)(1-z_{d,t}),\\
q^k_{d,t},w_{d,t}&\ge0,\quad z_{d,t}\in\{0,1\}.
\end{aligned}
$$

The current measured SOC initializes each update, and the daily midnight SOC is used as the planning terminal reference. For the two unresolved reduction-settlement interpretations, the final interval contract cost is

$$
F_A=p_tq^0_{d,t}+1.5p_t(q^k_{d,t}-q^0_{d,t})_+-0.5p_t(q^0_{d,t}-q^k_{d,t})_+,
$$

$$
F_B=p_tq^0_{d,t}+1.5p_t(q^k_{d,t}-q^0_{d,t})_++0.5p_t(q^0_{d,t}-q^k_{d,t})_+.
$$

The update model minimizes the sum of the selected \(F\) over \(\mathcal H_k\). Each interval is settled once against the original midnight plan; successive optimization objectives are not added. The realized daily bill adds fivefold emergency cost to the final contract cost.

For the corrected-PV extension, the raw PV forecast at release hour \(h\) is adjusted only when its raw value is positive:

$$
\widehat g^{\mathrm{corr}}_{d,t\mid k}=
\max\left\{0,\widehat g^{\mathrm{raw}}_{d,t\mid k}+\overline r_{h,28}\right\},
$$

where \(\overline r_{h,28}\) is the mean realized-minus-forecast error from the latest 28 days available at the decision time and with the same release hour. The correction is a forecasting pre-processing step; it does not alter the storage constraints, settlement function, or actual executor.

### 5.4.4 Model Solution

Six pre-specified policies are solved: no update, all 06:00/12:00/18:00 updates under rules A and B, and three single-update A policies. At each update, executed decisions remain fixed and the latest allowable PV version and actual SOC are supplied to a new remaining-horizon MILP. The all-update policy therefore solves four horizons per day, or 1,336 horizons over the 334-day period. HiGHS 1.14.0 is run with one thread, seed 0, a 120-second horizon limit, and a relative MIP-gap tolerance of \(10^{-9}\); no maximum iteration count is separately set. The formal supplementary-code number and official `result3.xlsx` export remain pending.

### 5.4.5 Results Analysis

Under rule A, retaining only the midnight forecast costs CNY 15,842,067.99, whereas using all three later forecast updates costs CNY 13,772,880.06. The all-update policy has a higher contract cost but a much lower emergency cost, reducing the realized bill by CNY 2,069,187.93 (13.061%) and lowering emergency purchases from 574,236.05 to 125,345.25 kWh. A feedback-only comparison costs CNY 13,934,357.97, showing that actual-SOC feedback and newly released PV information are jointly involved; the all-update difference must not be labelled as pure forecast value.

The 28-day, release-time-specific PV bias correction is selected in March, enabled on April 1, and then replayed continuously without an SOC reset. It lowers the 334-day rule-A all-update cost from CNY 13,772,880.06 to CNY 13,726,733.57. This CNY 46,146.49 cumulative gain includes 122 higher-cost days and is therefore stated as a conditional historical improvement rather than a per-day guarantee.

**Table 5. Principal Problem 3 comparisons over 334 days**

| Policy | Contract cost (CNY) | Emergency cost (CNY) | Realized cost (CNY) | Emergency purchase (kWh) |
|---|---:|---:|---:|---:|
| Midnight forecast only, rule A | 12,281,584.60 | 3,560,483.39 | 15,842,067.99 | 574,236.05 |
| All updates, raw PV, rule A | 13,053,598.95 | 719,281.11 | 13,772,880.06 | 125,345.25 |
| All updates, corrected PV, rule A | — | — | 13,726,733.57 | — |

### 5.4.6 Model Verification and Sensitivity Analysis

The main Q3 validator reports 110,401 passing independent checks and a separate feedback-control check reports 30,048 passing checks. It independently verifies allowed forecast versions, frozen load predictions, original commitments, actual state feedback, physical constraints, final-once settlement, and exported summaries. The maximum actual-balance residual is 0 kWh and the maximum planned-balance residual is \(1.735\times10^{-10}\) kWh, both within the \(10^{-6}\) kWh acceptance tolerance. Settlement-rule A/B, update-time ablations, and feedback-only control are mechanism comparisons, not general robustness proofs. The continuous correction is further checked at 14-, 28-, and 56-day windows, two efficiency conventions, and hard/soft terminal references; the evaluated comparisons retain positive cumulative correction gains but do not cover all parameter interactions.

## 5.5 Problem 4: Model Establishment and Solution

### 5.5.1 Modeling Rationale and Model Selection

Problem 4 repeats the Problem 2 and Problem 3 mechanisms when external-grid prices vary by interval. The main difficulty is information availability: Attachment 4 records realized prices but does not state that future prices are known when a plan is made. The implementable branch therefore uses a causal ordinary least-squares price forecast, while a perfect-price case is kept only as a labelled benchmark. Q4-2 retains the Problem 2 historical-PV mechanism; Q4-3 retains the Problem 3 released-PV and rolling-update mechanism.

### 5.5.2 Data Processing

The variable-price study uses the 48,096 evaluation intervals from Attachments 2–4, with Attachment 3 used only by the Q4-3 branch. At every permitted decision time, the price model is trained on the latest 28 completed days using two daily Fourier harmonics, one-day and seven-day price lags, and weekday indicators. Forecast prices are constrained below by \(10^{-6}\) CNY/kWh, a pre-declared numerical positivity rule rather than an estimate from future minima. Actual settlement always uses the Attachment 4 target-interval price. Q4-2 does not gain access to Attachment 3 simply because Q4-3 uses it.

### 5.5.3 Model Formulation

The Q4-2 planning objective replaces the fixed tariff in Problem 2 with the causal forecast price:

$$
\widehat p_{u\mid k}=\max\left\{10^{-6},\beta_0+
\sum_{j=1}^{2}\left[a_j\sin(2\pi j\varphi_u)+b_j\cos(2\pi j\varphi_u)\right]
+\beta_1p_{u-1\mathrm{d}}+\beta_7p_{u-7\mathrm{d}}
+\sum_{r=1}^{6}\gamma_rI\{\mathrm{weekday}(u)=r\}\right\},
$$

where \(\varphi_u\) is the within-day price phase; the coefficients are estimated only from the stated trailing window, and every lagged price is available when the forecast is formed. The Q4-2 planning objective replaces the fixed tariff in Problem 2 with this causal forecast price:

$$
\min J^{\mathrm{plan}}_{4-2,d}=\sum_{t=1}^{T}\widehat p_{d,t\mid0}q^0_{d,t},
$$

subject to the same power-balance, SOC, capacity, power, non-negativity, and binary-mode constraints in Section 5.3.3. Q4-3 retains the rolling formulation in Section 5.4.3, substituting \(\widehat p_{d,t\mid k}\) into the selected contract-cost function. Both branches settle actual cost with the realized price:

$$
J_{4-2}=\sum_{d,t}p_{d,t}(q^0_{d,t}+5e_{d,t}),
$$

$$
J_{4-3}=\sum_{d,t}\left[F(\bar q_{d,t};q^0_{d,t},p_{d,t})+5p_{d,t}e_{d,t}\right].
$$

Thus, forecast prices guide the plan but never replace actual prices in the bill. The perfect-price benchmark changes only the planning-price input and remains subject to the same demand/PV uncertainty and actual execution rule.

### 5.5.4 Model Solution

Nine pre-specified policies are evaluated: three Q4-2 price-information cases and six Q4-3 cases covering no update, all updates under rules A/B, frozen-at-midnight price updates, fixed-price input, and perfect-price input. The Q4-3 corrected-PV transfer is evaluated only against the causally priced rule-A all-update policy; Q4-2 remains within its historical-PV information boundary. The same HiGHS environment, one-thread setting, seed 0, 120-second horizon limit, and MIP feasibility/gap criteria are used. The 28-day price-model window and the nine policy families are fixed before the Q4 calculation, although the study remains retrospective because Q2/Q3 annual outcomes were already known. No formal `result4-2.xlsx` or `result4-3.xlsx` export has yet been produced.

### 5.5.5 Results Analysis

The causal-price Q4-2 policy costs CNY 17,030,881.70, compared with CNY 17,073,742.68 for the otherwise matched fixed-price-input policy, a CNY 42,860.98 reduction. In Q4-3, however, the causal-price all-update A policy costs CNY 14,534,062.64, CNY 6,183.03 more than its matched fixed-price-input comparison. The direction changes across branches, so price adaptation is not presented as a universally beneficial modification. When the Problem 3 28-day PV correction is transferred to the causal-price Q4-3 branch, the realized cost falls to CNY 14,492,279.55, a CNY 41,783.10 reduction under the stated scenario.

**Table 6. Matched variable-price comparisons over 334 days**

| Branch and policy | Realized cost (CNY) | Matched reference (CNY) | Difference (CNY) |
|---|---:|---:|---:|
| Q4-2, causal price forecast | 17,030,881.70 | 17,073,742.68 | −42,860.98 |
| Q4-3, all updates A with causal price | 14,534,062.64 | 14,527,879.61 | +6,183.03 |
| Q4-3, all updates A with corrected PV | 14,492,279.55 | 14,534,062.64 | −41,783.10 |

### 5.5.6 Model Verification and Sensitivity Analysis

The Q4 validator records 211,834 passing checks across the nine policies, including source-price separation, forecast information cutoffs, physical constraints, commitment versions, actual-price settlement, and ledger reconstruction. Thirty-six representative update horizons are independently checked with LP relaxations; the maximum MILP-minus-LP lower-bound difference is \(2.910\times10^{-11}\) CNY and the largest LP feasibility residual is \(1.819\times10^{-12}\). The perfect-price case is not an achievable lower bound on actual cost, and Q4-2/Q4-3 are not treated as a pure update-value comparison because their PV information differs. The price-information rule, settlement timing, and official workbook time mapping remain the principal unresolved sensitivities.

# 6 Verification, Sensitivity, and Scope Limits

Independent validation re-reads exported ledgers rather than relying on the optimizer's in-memory variables. It checks energy balance, SOC recursion, capacity and power limits, charging/discharging exclusivity, cross-day continuity, source-data matching, information cutoffs, commitment versions, fee decomposition, and required tables. The Q1 checks confirm agreement between the reported purchase cost and a separate recomputation. The Q2 and Q3 validators separately reconstruct forecast availability and actual execution. The extended continuous-replay evidence records 429,222 independent checks and 160 sampled LP lower-bound checks; these support internal arithmetic and implementation consistency, not a general proof that the MILP and LP are equivalent or that the strategy is globally optimal over an uncertain year.

Sensitivity work retains the 14-, 28-, and 56-day PV-bias windows, the two efficiency conventions, hard versus soft planning terminal conditions, and the Q4-3 variable-price setting. The six evaluated paired settings all show lower cumulative cost after the bias correction, but the 28-day window remains the primary setting because it was selected before this continuous replay rather than because it has the largest subsequent gain. Day-level paired savings are also summarized using consecutive-date block resampling. Such intervals describe variation in the observed historical path under the declared resampling design; they are not future-profit probabilities, distributionally robust guarantees, or external validation on an unseen year.

The model excludes battery degradation, communication costs, measurement delay, and second-level converter dynamics because the statement supplies no parameters for them. The optimality claim for Problem 1 applies only to its deterministic finite-horizon formulation and the selected assumptions. Results for Problems 2–4 are retrospective closed-loop simulations over the required February–December period, not proof of performance in another year. The current interpretation of timestamp alignment, storage efficiency, price availability, refund treatment, and revision settlement must be confirmed before final numerical results are presented as an official submission.

# 7 Model Evaluation, Improvement, and Generalization

## 7.1 Model Summary

This study combines a deterministic battery-dispatch MILP, causal load/PV and price forecasting, and rolling re-optimization to address four progressively more information-constrained microgrid scheduling tasks. Problem 1 establishes the physically constrained day-ahead dispatch core; Problem 2 tests the consequences of a fixed commitment under realized load and PV deviations; Problem 3 introduces permitted PV-forecast revisions and actual-SOC feedback; and Problem 4 extends the same framework to time-varying electricity prices. Their linkage is explicit: the same energy balance, battery state, power limits, and realized-execution ledger are retained across questions, while later questions add only the information and settlement mechanisms allowed by their scenarios. Independent ledger reconstruction, physical-feasibility checks, and selected sensitivity comparisons support internal consistency of the reported results, but do not establish out-of-sample economic performance.

## 7.2 Strengths of the Model

(1) The formulation is closely matched to the operational structure of the problem. The dispatch model jointly represents grid purchases, PV availability, charging, discharging, energy storage, and non-simultaneous battery modes. In particular, the surplus-disposal constraint prevents regular grid purchases from being treated as disposable energy. This makes the cost objective and the physical balance consistent with the stated microgrid setting rather than treating storage arbitrage as an unconstrained accounting exercise.

(2) The information boundary is handled explicitly. Forecasts are trained only on observations available at the relevant decision time, released PV versions are tied to their release times, and executed intervals are frozen during rolling updates. This design distinguishes a feasible causal policy from a perfect-information benchmark. The independent validators check forecast cutoffs, commitment versions, and actual-price settlement; Q4 alone records 211,834 passing checks, while the extended continuous-replay checks total 429,222.

(3) The four questions form a reusable and auditable sequence. Rather than changing the physical model from question to question, the analysis preserves the common battery state and realized-operation rules, then adds a day-ahead commitment, revision settlement, and price forecast in turn. This isolates the source of each comparison. For example, the feedback-only control in Problem 3 avoids attributing the all-update outcome solely to newly released PV information.

(4) The study reports unfavorable as well as favorable evidence. The January-selected forecast combination in Problem 2 is shown to have a higher annual realized cost than the matched seasonal baseline, and causal price adaptation has opposite directions in the Q4-2 and Q4-3 comparisons. Reporting these outcomes limits overstatement and identifies which mechanisms require further validation.

## 7.3 Limitations of the Model

(1) The results depend on unresolved interpretation and data-mapping issues. In particular, the official workbook timestamp convention, the treatment of purchase reductions in settlement, the battery-efficiency convention, and future-price availability require confirmation. These choices can alter the ledger or objective and therefore limit the use of current numerical outputs as final submission results.

(2) The physical model deliberately omits battery degradation, converter transients, communication delays, measurement errors, and possible export or curtailment rules beyond the declared surplus-disposal treatment. This reduction keeps the MILP identifiable from the supplied data, but may bias cost and cycling conclusions if these omitted factors are material in a real deployment. The conclusions therefore apply to interval-level energy scheduling under the stated battery abstraction.

(3) Forecast and correction specifications are based on one historical microgrid series and limited rolling windows. The 28-day PV-bias correction has positive cumulative gains in the evaluated paired settings, but it also contains higher-cost days and has not been externally tested on another year or site. Likewise, the price model is a causal OLS specification, not evidence that the selected predictors are universally sufficient.

## 7.4 Improvements and Generalization

The first improvement priority is to reconcile the official time map and settlement wording, then regenerate the five required workbooks from a single versioned ledger. Once the data definition is fixed, degradation cost, battery-side versus bus-side power limits, metering uncertainty, and explicit PV-export or curtailment options can be introduced as calibrated variables or constraints. Forecasting can then be assessed with rolling out-of-sample periods and alternative models selected by operational cost as well as forecast error. A robust or distributionally robust rolling-dispatch extension would be appropriate only after forecast-error scenarios, their dependence structure, and a decision-maker's risk tolerance are supported by data; it should not be claimed from the current deterministic replay.

The framework can be generalized to other behind-the-meter storage systems, industrial parks, charging stations, and renewable microgrids that face interval energy balance, limited storage, uncertain local generation, and tariff-dependent purchases. The core state-transition and dispatch constraints can be reused, whereas load, renewable generation, price, storage capacity, power rating, efficiency, settlement rule, and permitted update times must be recalibrated for the new setting. A new application may also require demand charges, multiple storage units, export tariffs, network limits, or emissions objectives; these should be added to the objective and constraints rather than assumed to be covered by the present single-battery formulation. Such extension is a modelling route, not a demonstrated performance guarantee.

## Evidence Still Required

- Confirm the Attachment 5 time mapping and the official interpretation of price availability and purchase-reduction settlement.
- Produce, independently re-read, and reconcile the five required official `.xlsx` workbooks with the manuscript tables.
- Add rolling out-of-sample or cross-site evidence before claiming forecasting or economic performance beyond the evaluated February–December historical path.

## Three Highest-Priority Revisions

1. Resolve the timestamp, efficiency, and settlement definitions before freezing any final numerical conclusion.
2. Generate the official workbooks and make their row-level totals reproduce every reported table.
3. Standardize formulas, notation, table/figure references, citations, and submission-format requirements across the complete manuscript.

# 8 Required Deliverables and Editorial Status

The paper now contains the common model logic, result summaries, the Q2 failure comparison, the Q3 update and correction evidence, the Q4 variable-price evidence, and their applicable limitations. Three material deliverables remain incomplete: (1) map all internal ten-minute keys to the official Attachment 5 rows after the timestamp convention is confirmed; (2) export and independently re-read the five required `.xlsx` workbooks, including the four specified dates within the corresponding question sections; and (3) unify equations, symbols, figure and table numbering, citations, and final anonymity/page-format requirements across the full manuscript. These are submission blockers, not cosmetic tasks.
