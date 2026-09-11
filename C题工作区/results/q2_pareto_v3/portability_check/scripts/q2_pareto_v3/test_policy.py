import unittest
import numpy as np
import pandas as pd
from policy import empirical_cvar, guard_mask, profile_delta, simulate


class Tests(unittest.TestCase):
    def test_discrete_tail_fraction_and_atoms(self):
        np.testing.assert_allclose(empirical_cvar(np.array([[0.,10.,20.],[7.,7.,7.]]),.5),[50/3,7])
        np.testing.assert_allclose(empirical_cvar(np.array([[0.,10.,20.]]),.9),[20])

    def test_tail_guard_rejects_same_mean_riskier_candidate(self):
        ordinary=np.array([100.,90.,90.,110.,90.])
        emergency=np.array([[5.,5.],[0.,10.],[4.,4.],[4.,4.],[4.,4.]])
        energy=np.array([[2000.,2000.],[2000.,2000.],[2000.,2000.],[2000.,2000.],[1900.,1900.]])
        np.testing.assert_array_equal(guard_mask(ordinary,emergency,energy,'tail',.9),[True,False,True,False,False])
        np.testing.assert_array_equal(guard_mask(ordinary,emergency,energy,'mean',.9),[True,True,True,False,False])
        np.testing.assert_array_equal(guard_mask(ordinary,emergency,energy,'none',.9),[True]*5)

    def test_hour_profile_uses_only_completed_past_rows(self):
        rows=[]
        for d in range(1,10):
            for t in range(144):rows.append(dict(date=f'2025-01-{d:02}',slot_id=t+1,residual_available_time=str(pd.Timestamp(f'2025-01-{d:02}')+pd.Timedelta(days=1)),net_residual_kwh=float(d+100*(t//6))))
        a=pd.DataFrame(rows);profile=[.5]*24;profile[20]=.9
        delta=profile_delta(a,'2025-01-09',profile)
        self.assertAlmostEqual(delta[0],4.5)
        self.assertAlmostEqual(delta[120],2008.)
        a.loc[a.date=='2025-01-09','net_residual_kwh']=1e6
        np.testing.assert_array_equal(delta,profile_delta(a,'2025-01-09',profile))

    def test_sparse_recent_history_stops_instead_of_zero_risk(self):
        rows=[]
        for date in pd.date_range('2025-01-02','2025-01-09'):
            for slot in range(1,145):
                rows.append(dict(date=str(date.date()),slot_id=slot,
                    residual_available_time=str(date+pd.Timedelta(days=1)),net_residual_kwh=20.))
        with self.assertRaisesRegex(ValueError,'seven completed'):
            profile_delta(pd.DataFrame(rows),'2025-02-05',[.8]*24)

    def test_scenario_actions_cannot_see_future(self):
        grid=np.array([[100.,100.,100.]]);net=np.array([[50.,200.,100.]])
        x=simulate(grid,net,np.ones(3),2000.,0.,traces=True)
        net[0,2]=10000.;y=simulate(grid,net,np.ones(3),2000.,0.,traces=True)
        for key in x['trace']:np.testing.assert_array_equal(x['trace'][key][...,:2],y['trace'][key][...,:2])
        self.assertGreater(y['emergency_fee'][0,0],x['emergency_fee'][0,0])


if __name__=='__main__':unittest.main(verbosity=2)
