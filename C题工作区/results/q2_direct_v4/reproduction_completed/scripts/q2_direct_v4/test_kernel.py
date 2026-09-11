import unittest
import numpy as np
from kernel import evaluate


def scalar(q, net, price, initial, kappa, mu):
    fees, ends = [], []
    for row in net:
        e = initial; fee = 0.
        for g, n, p in zip(q, row, price):
            v = g - n
            if v >= 0:
                e += .9 * min(v, 5000/6, max((10800-e)/.9, 0))
            else:
                d = min(-v, 5000/6, max(.9*(e-1200), 0))
                fee += 5*p*max(-v-d, 0)
                e -= d/.9
        fees.append(fee); ends.append(e)
    return np.dot(q, price) + kappa/5*np.mean(fees) - mu*(np.mean(ends)-initial), fees, ends


class KernelTest(unittest.TestCase):
    def test_hand_and_boundaries(self):
        for initial in [1200., 6000., 10800.]:
            q=np.array([0., 1800., 0., 400.]); p=np.array([1., .4, 1.2, .5])
            n=np.array([[1000., 0., 11000., 0.], [0., 0., 0., 500.]])
            r=evaluate(q,n,p,initial,6.25,.38232)
            expected=scalar(q,n,p,initial,6.25,.38232)
            self.assertAlmostEqual(r['score'],expected[0],places=8)
            np.testing.assert_allclose(r['emergency_fee'],expected[1],atol=1e-8)
            np.testing.assert_allclose(r['end_energy'],expected[2],atol=1e-8)

    def test_gradient_away_from_kinks(self):
        rng=np.random.default_rng(20260915)
        q=rng.uniform(25,1400,144); n=rng.uniform(-300,2100,(7,144)); p=rng.uniform(.3,1.2,144)
        r=evaluate(q,n,p,6417.123,6.25,.38232)
        expected=scalar(q,n,p,6417.123,6.25,.38232)
        self.assertAlmostEqual(r['score'],expected[0],places=7)
        fd=[]
        for i in range(144):
            delta=np.zeros(144);delta[i]=1e-4
            fd.append((scalar(q+delta,n,p,6417.123,6.25,.38232)[0]-scalar(q-delta,n,p,6417.123,6.25,.38232)[0])/2e-4)
        np.testing.assert_allclose(r['gradient'],fd,atol=5e-6,rtol=1e-5)

    def test_prefix(self):
        q=np.full(144,400.);n=np.full((2,144),500.); p=np.ones(144)
        mutated=n.copy();mutated[:,72:]+=1000
        a=evaluate(q[:72],n[:,:72],p[:72],6000.)
        b=evaluate(q[:72],mutated[:,:72],p[:72],6000.)
        np.testing.assert_array_equal(a['end_energy'],b['end_energy'])
        self.assertGreater(evaluate(q,mutated,p,6000.)['score'],evaluate(q,n,p,6000.)['score'])


if __name__ == '__main__': unittest.main()
