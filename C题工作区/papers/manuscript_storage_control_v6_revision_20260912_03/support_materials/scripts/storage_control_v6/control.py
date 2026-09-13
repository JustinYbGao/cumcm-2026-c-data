"""Causal bus-side interval dispatch with a preissued storage reserve threshold."""


def execute_interval(grid, load, pv, energy, reserve, eta_c=.9, eta_d=.9):
    """Balance this interval without charging from emergency electricity.

    ``reserve`` limits deficit discharge; it is not an inventory target that must
    be reached. An inventory already below reserve remains available for surplus
    charging, but no energy is discharged until it exceeds reserve.
    """
    net = grid + pv - load
    c = d = emergency = surplus = 0.
    if net >= 0:
        c = min(net, 5000 / 6, max(0., (10800 - energy) / eta_c))
        surplus = net - c
    else:
        d = min(-net, 5000 / 6, max(0., eta_d * (energy - reserve)))
        emergency = -net - d
    unused_grid = min(grid, surplus)
    return {'charge_actual_kwh': c, 'discharge_actual_kwh': d,
            'emergency_kwh': emergency, 'surplus_kwh': surplus,
            'unused_grid_kwh': unused_grid,
            'pv_curtailment_kwh': surplus - unused_grid,
            'energy_start_actual_kwh': energy,
            'energy_end_actual_kwh': energy + eta_c * c - d / eta_d,
            'reserve_threshold_kwh': reserve}
