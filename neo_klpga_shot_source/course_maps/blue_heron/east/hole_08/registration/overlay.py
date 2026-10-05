import json, numpy as np
from PIL import Image, ImageDraw

RES = json.load(open('/tmp/claude-0/-home-user-Neo-golf-performance-/bee7b372-e13f-52b9-816d-77030a003a04/scratchpad/h8reg/transform_results.json'))
sim = RES['results']['similarity']['params']
R = np.array(sim['R']); s = sim['scale']; t = np.array(sim['t'])

def transform(p):
    return s*R@np.array(p)+t

DEBUG = json.load(open('/home/user/Neo-golf-performance-/neo_klpga_shot_source/artifacts/blue_heron_h8_debug.json'))

LIE_COLOR = {
  "FAIRWAY": (37,99,235), "ROUGH": (161,98,7), "GREEN": (22,163,74), "BUNKER": (234,179,8),
  "GREENSIDE_BUNKER": (202,138,4), "PENALTY_AREA": (14,165,233), "LOST_BALL": (220,38,38),
  "PENALTY_STROKE": (220,38,38), "FRINGE": (101,163,13), "HOLED": (17,24,39), "OB": (220,38,38),
}

bh_path = '/home/user/Neo-golf-performance-/neo_klpga_shot_source/course_maps/blue_heron/east/hole_08/visual.png'

def render(players, out_path, title=None):
    im = Image.open(bh_path).convert("RGBA")
    draw = ImageDraw.Draw(im)
    for pname, rec in players.items():
        shots = rec['shots']
        pts = []
        for sh in shots:
            bh_pt = transform((sh['map_x'], sh['map_y']))
            pts.append(bh_pt)
        for i in range(1,len(pts)):
            draw.line([tuple(pts[i-1]), tuple(pts[i])], fill=(20,20,20,230), width=2)
        for i,(sh,pt) in enumerate(zip(shots,pts)):
            col = LIE_COLOR.get(sh['state_name'], (100,100,100))
            r=9
            draw.ellipse([pt[0]-r,pt[1]-r,pt[0]+r,pt[1]+r], fill=col+(255,), outline=(255,255,255,255), width=2)
            draw.text((pt[0]-3,pt[1]-5), str(sh['shot']), fill=(255,255,255,255))
    im.save(out_path)
    print('wrote', out_path)

OUT = '/tmp/claude-0/-home-user-Neo-golf-performance-/bee7b372-e13f-52b9-816d-77030a003a04/scratchpad/h8reg'
players_all = {k:v for k,v in DEBUG['players'].items()}
render(players_all, f'{OUT}/h8_registration_overlay_all.png')
for k,v in DEBUG['players'].items():
    render({k:v}, f'{OUT}/h8_overlay_{k}.png')

# print transformed coordinates for sanity/red-team check
for k,v in DEBUG['players'].items():
    print(f"\n=== {k} ===")
    for sh in v['shots']:
        bh_pt = transform((sh['map_x'], sh['map_y']))
        print(f"  shot {sh['shot']} {sh['state_name']:<10} klpga_map=({sh['map_x']:.1f},{sh['map_y']:.1f}) -> bh=({bh_pt[0]:.1f},{bh_pt[1]:.1f})")
