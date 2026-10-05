from PIL import Image
import json

def water_mask(img):
    img = img.convert("RGBA")
    w,h = img.size
    px = img.load()
    pts = []
    for y in range(h):
        for x in range(w):
            r,g,b,a = px[x,y]
            if a < 10: continue
            is_blue = b > 140 and b > r + 15 and b > g - 10 and g < 220
            if is_blue:
                pts.append((x,y))
    return pts

def centroid_bbox(pts):
    if not pts: return None
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return dict(n=len(pts), centroid=[round(sum(xs)/len(xs),1), round(sum(ys)/len(ys),1)],
                bbox=[min(xs),min(ys),max(xs),max(ys)])

klpga = Image.open('/home/user/Neo-golf-performance-/neo_klpga_shot_source/hole_images/hole_8.png')
bh = Image.open('/home/user/Neo-golf-performance-/neo_klpga_shot_source/course_maps/blue_heron/east/hole_08/visual.png')

print("=== KLPGA hole_8.png water ===")
kp = water_mask(klpga)
print(json.dumps(centroid_bbox(kp), indent=2))

print("=== BH visual.png water (all blue, both lobes) ===")
bp = water_mask(bh)
print(json.dumps(centroid_bbox(bp), indent=2))

# cluster BH water into connected-ish groups by simple x-split since there appear to be 2 lobes
import collections
def cluster_by_proximity(pts, gap=15):
    pts = sorted(pts)
    clusters = []
    cur = [pts[0]]
    for p in pts[1:]:
        if abs(p[0]-cur[-1][0]) <= gap:
            cur.append(p)
        else:
            clusters.append(cur); cur=[p]
    clusters.append(cur)
    return clusters

# simpler: 2D flood-ish via grid buckets
def connected_components(pts):
    ptset = set(pts)
    seen = set()
    comps = []
    for p in pts:
        if p in seen: continue
        stack=[p]; comp=[]
        seen.add(p)
        while stack:
            cx,cy = stack.pop()
            comp.append((cx,cy))
            for dx in (-1,0,1):
                for dy in (-1,0,1):
                    np_ = (cx+dx,cy+dy)
                    if np_ in ptset and np_ not in seen:
                        seen.add(np_); stack.append(np_)
        comps.append(comp)
    return comps

comps = connected_components(bp)
comps.sort(key=lambda c: -len(c))
print(f"BH water connected components: {len(comps)}, sizes={[len(c) for c in comps[:5]]}")
for i,c in enumerate(comps[:3]):
    print(f"  component {i}:", centroid_bbox(c))

print()
print("=== BH tee marker dots (red/white/orange/blue circles near bottom) ===")
def find_color_blobs(img, test_fn, region=None):
    img = img.convert("RGBA")
    w,h = img.size
    px = img.load()
    pts=[]
    x0,x1,y0,y1 = region if region else (0,w,0,h)
    for y in range(y0,y1):
        for x in range(x0,x1):
            r,g,b,a = px[x,y]
            if a<10: continue
            if test_fn(r,g,b):
                pts.append((x,y))
    return pts

def comps_of(pts):
    return connected_components(pts) if pts else []

bh_full = Image.open('/home/user/Neo-golf-performance-/neo_klpga_shot_source/course_maps/blue_heron/east/hole_08/visual.png')
# red marker: strong red, low green/blue
red_pts = find_color_blobs(bh_full, lambda r,g,b: r>180 and g<90 and b<90, region=(0,527,400,704))
red_comps = sorted(comps_of(red_pts), key=lambda c:-len(c))
print("red tee marker candidates:", [centroid_bbox(c) for c in red_comps[:3]])

white_pts = find_color_blobs(bh_full, lambda r,g,b: r>235 and g>235 and b>235, region=(200,350,400,704))
# white is tricky (background also white) -- restrict tightly to near-tee region and expect a compact round blob; will cross check visually instead
orange_pts = find_color_blobs(bh_full, lambda r,g,b: r>220 and 100<g<190 and b<90, region=(0,527,400,704))
orange_comps = sorted(comps_of(orange_pts), key=lambda c:-len(c))
print("orange tee marker candidates:", [centroid_bbox(c) for c in orange_comps[:3]])

blue_dot_pts = find_color_blobs(bh_full, lambda r,g,b: b>150 and b>r+40 and b>g+40 and r<100, region=(0,527,550,704))
blue_comps = sorted(comps_of(blue_dot_pts), key=lambda c:-len(c))
print("blue tee marker candidates:", [centroid_bbox(c) for c in blue_comps[:3]])

print()
print("=== KLPGA tee (small dark-bordered circle at far left) ===")
klpga_full = Image.open('/home/user/Neo-golf-performance-/neo_klpga_shot_source/hole_images/hole_8.png')
# crop far-left region and inspect distinct colors
region = klpga_full.crop((0,180,60,260))
region = region.convert("RGB")
colors = region.getcolors(maxcolors=100000)
colors.sort(key=lambda c:-c[0])
print("top colors in left tee region:", colors[:8])
