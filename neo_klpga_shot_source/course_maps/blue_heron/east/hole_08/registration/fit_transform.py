import numpy as np
import json

LANDMARKS = [
    dict(id="L1_TEE", desc="tee area (KLPGA single tee pad vs BH centroid of red/orange/blue tee markers -- structural mismatch, lower confidence)",
         klpga=(14,194), bh=(276,534), confidence="LOW"),
    dict(id="L2_FAIRWAY_LANDING_CENTER", desc="textured fairway landing-zone stripe, centroid",
         klpga=(325,152), bh=(242,315), confidence="HIGH"),
    dict(id="L3_FAIRWAY_LANDING_TEE_END", desc="landing-zone stripe, tee-side end",
         klpga=(228,158), bh=(242,380), confidence="MEDIUM"),
    dict(id="L4_FAIRWAY_LANDING_GREEN_END", desc="landing-zone stripe, green-side end",
         klpga=(425,142), bh=(242,250), confidence="MEDIUM"),
    dict(id="L5_WATER_CENTROID", desc="primary water hazard centroid (KLPGA single blob matched to BH's near/green-side lobe specifically, not the combined 2-lobe shape -- see note)",
         klpga=(524,193), bh=(268,183), confidence="MEDIUM"),
    dict(id="L6_GREEN_CENTER", desc="green surface centroid (flag/pin area)",
         klpga=(603,218), bh=(293,123), confidence="HIGH"),
]

for l in LANDMARKS:
    print(l['id'], l['klpga'], '->', l['bh'], l['confidence'])

src = np.array([l['klpga'] for l in LANDMARKS], dtype=float)
dst = np.array([l['bh'] for l in LANDMARKS], dtype=float)

def fit_similarity(src, dst):
    # Umeyama: finds s,R,t minimizing sum |s*R*src+t - dst|^2
    n = len(src)
    mu_src, mu_dst = src.mean(0), dst.mean(0)
    src_c, dst_c = src-mu_src, dst-mu_dst
    cov = (dst_c.T @ src_c) / n
    U,S,Vt = np.linalg.svd(cov)
    D = np.eye(2)
    if np.linalg.det(U @ Vt) < 0:
        D[1,1] = -1
    R = U @ D @ Vt
    var_src = (src_c**2).sum()/n
    s = np.trace(np.diag(S) @ D) / var_src
    t = mu_dst - s*R@mu_src
    def apply(p):
        return s*R@np.array(p)+t
    angle = np.degrees(np.arctan2(R[1,0], R[0,0]))
    return apply, dict(scale=float(s), rotation_deg=float(angle), R=R.tolist(), t=t.tolist())

def fit_affine(src, dst):
    n = len(src)
    A = np.zeros((2*n,6))
    b = np.zeros(2*n)
    for i,(p,q) in enumerate(zip(src,dst)):
        A[2*i]   = [p[0],p[1],1,0,0,0]
        A[2*i+1] = [0,0,0,p[0],p[1],1]
        b[2*i]=q[0]; b[2*i+1]=q[1]
    params, *_ = np.linalg.lstsq(A,b,rcond=None)
    a,bb,c,d,e,f = params
    def apply(p):
        x,y = p
        return np.array([a*x+bb*y+c, d*x+e*y+f])
    return apply, dict(params=params.tolist())

def fit_homography(src, dst):
    n = len(src)
    A = np.zeros((2*n,9))
    for i,(p,q) in enumerate(zip(src,dst)):
        x,y = p; u,v = q
        A[2*i]   = [-x,-y,-1,0,0,0,x*u,y*u,u]
        A[2*i+1] = [0,0,0,-x,-y,-1,x*v,y*v,v]
    U,S,Vt = np.linalg.svd(A)
    h = Vt[-1]
    H = h.reshape(3,3)
    def apply(p):
        x,y = p
        vec = H @ np.array([x,y,1.0])
        return np.array([vec[0]/vec[2], vec[1]/vec[2]])
    return apply, dict(H=H.tolist())

def residuals(apply_fn, src, dst):
    errs = []
    for p,q in zip(src,dst):
        pred = apply_fn(p)
        err = np.linalg.norm(pred-np.array(q))
        errs.append(err)
    return errs

def loo_residuals(fit_fn, src, dst):
    n = len(src)
    errs = []
    for i in range(n):
        mask = [j for j in range(n) if j!=i]
        apply_fn, _ = fit_fn(src[mask], dst[mask])
        pred = apply_fn(src[i])
        err = np.linalg.norm(pred-dst[i])
        errs.append(err)
    return errs

print()
results = {}
for name, fit_fn in [("similarity", fit_similarity), ("affine", fit_affine), ("homography", fit_homography)]:
    apply_fn, params = fit_fn(src, dst)
    train_err = residuals(apply_fn, src, dst)
    loo_err = loo_residuals(fit_fn, src, dst)
    results[name] = dict(
        params=params,
        train_residuals=[round(e,1) for e in train_err],
        train_median=round(float(np.median(train_err)),1),
        train_max=round(float(np.max(train_err)),1),
        loo_residuals=[round(e,1) for e in loo_err],
        loo_median=round(float(np.median(loo_err)),1),
        loo_max=round(float(np.max(loo_err)),1),
    )
    print(f"=== {name} ===")
    print(f"  train: median={results[name]['train_median']} max={results[name]['train_max']} per-point={results[name]['train_residuals']}")
    print(f"  LOO:   median={results[name]['loo_median']} max={results[name]['loo_max']} per-point={results[name]['loo_residuals']}")
    if name=='similarity':
        print(f"  scale={params['scale']:.4f} rotation={params['rotation_deg']:.2f}deg")

json.dump(dict(landmarks=LANDMARKS, results=results), open('/tmp/claude-0/-home-user-Neo-golf-performance-/bee7b372-e13f-52b9-816d-77030a003a04/scratchpad/h8reg/transform_results.json','w'), indent=2)
