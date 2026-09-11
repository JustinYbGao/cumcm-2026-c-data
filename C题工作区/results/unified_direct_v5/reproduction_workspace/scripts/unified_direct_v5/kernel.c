#include <math.h>
#include <stdlib.h>

double objective(int S, int T, const double *q, const double *net, const double *p,
                 double initial, double kappa, double mu, double *grad,
                 double *fees, double *end) {
    double *buf = malloc(4 * (size_t)T * sizeof(double));
    if (!buf) return NAN;
    double *a=buf, *b=buf+T, *ue=buf+2*T, *uq=buf+3*T;
    const double eta=.9, power=5000./6.;
    double result=0.;
    for (int t=0;t<T;t++) { grad[t]=p[t]; result+=q[t]*p[t]; }
    for (int s=0;s<S;s++) {
        double e=initial, fee=0.;
        for (int t=0;t<T;t++) {
            double v=q[t]-net[s*T+t];
            ue[t]=0.; uq[t]=0.;
            if (v>=0.) {
                double space=fmax((10800.-e)/eta,0.);
                double c=fmin(fmin(v,power),space);
                if (v<=power && v<=space) {a[t]=1.; b[t]=eta;}
                else if (power<=space) {a[t]=1.; b[t]=0.;}
                else {a[t]=0.; b[t]=0.;}
                e+=eta*c;
            } else {
                double deficit=-v, avail=fmax(eta*(e-1200.),0.);
                double d=fmin(fmin(deficit,power),avail);
                fee+=5.*p[t]*fmax(deficit-d,0.);
                if (deficit<=power && deficit<=avail) {a[t]=1.; b[t]=1./eta;}
                else if (power<=avail) {a[t]=1.; b[t]=0.; uq[t]=-1.;}
                else {a[t]=0.; b[t]=0.; ue[t]=-eta; uq[t]=-1.;}
                e-=d/eta;
            }
        }
        fees[s]=fee; end[s]=e;
        result+=(kappa/5.*fee-mu*(e-initial))/S;
        double adjoint=-mu;
        for (int t=T-1;t>=0;t--) {
            grad[t]+=(kappa*p[t]*uq[t]+adjoint*b[t])/S;
            adjoint=kappa*p[t]*ue[t]+adjoint*a[t];
        }
    }
    free(buf);
    return result;
}
