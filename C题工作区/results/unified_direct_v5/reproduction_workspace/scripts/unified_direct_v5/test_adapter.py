"""Independent arithmetic checks for the new objective adapter."""
import unittest
import numpy as np


class AdapterTests(unittest.TestCase):
    def test_final_contract_and_greedy_emergency(self):
        from policy import evaluate
        q=np.array([80.,120.,100.]); q0=np.full(3,100.); p=np.ones(3)
        r=evaluate(q,np.array([[180.,120.,100.]]),p,1200.,q0=q0,mu=0.)
        self.assertAlmostEqual(r['ordinary'],320.)
        self.assertAlmostEqual(r['emergency_fee'][0],500.)
        self.assertAlmostEqual(r['score'],820.)
        self.assertAlmostEqual(r['end_energy'][0],1200.)

    def test_no_free_emergency_charging(self):
        from policy import evaluate
        r=evaluate(np.array([0.,0.]),np.array([[1000.,-100.]]),np.ones(2),1200.,mu=0.)
        self.assertAlmostEqual(r['emergency_fee'][0],5000.)
        self.assertAlmostEqual(r['end_energy'][0],1290.)

    def test_gradient_and_scaling(self):
        from policy import evaluate
        rng=np.random.default_rng(8409)
        for T in (36,72,108,144):
            q=rng.uniform(50,400,T); net=rng.uniform(-1600,1900,(11,T));p=rng.uniform(.2,1.5,T)
            q0=q+rng.choice([-1,1],T)*20
            r=evaluate(q,net,p,6131.32,q0=q0)
            grad=[]
            for t in range(T):
                a=q.copy();b=q.copy();a[t]+=.001;b[t]-=.001
                grad.append((evaluate(a,net,p,6131.32,q0=q0)['score']-evaluate(b,net,p,6131.32,q0=q0)['score'])/.002)
            self.assertLess(np.max(np.abs(np.array(grad)-r['gradient'])),1e-5)
            # x=q/1000 and f=J/10000 have gradient .1*dJ/dq.
            a=q.copy();b=q.copy();a[0]+=.001;b[0]-=.001
            scaled=(evaluate(a,net,p,6131.32,q0=q0)['score']/10000-evaluate(b,net,p,6131.32,q0=q0)['score']/10000)/(2e-6)
            self.assertAlmostEqual(scaled,.1*r['gradient'][0],places=6)


if __name__=='__main__': unittest.main()
