"""무료 에셋 라이브러리 (Poly Haven, 전부 CC0).

시스템 파이썬으로 실행:  python lib/assets.py            -> SETS 전부 받기
                         python lib/assets.py tex rock_07  -> 하나만
블렌더 안에서는 path()/catalog() 만 씀 (네트워크 X).

카탈로그(assets/catalog.json): id -> {type, category, license, res, files, bytes, tags}
- 라이선스: Poly Haven 은 모든 자산이 CC0 (https://polyhaven.com/license) 라 상업 사용·수정 자유, 출처 표기 의무 없음.
- 메모리 관리: bytes(디스크)와 res 를 기록 -> 장면 조립 시 텍스처 해상도를 줄일지 판단.
"""
import json
import os
import sys
import urllib.request

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
API = "https://api.polyhaven.com"
UA = {"User-Agent": "asset-fetch/1.0"}

# 카테고리별 기본 세트 (주제가 바뀌면 여기에 추가만 하면 됨)
SETS = {
    "tex": {
        "street": [("cobblestone_floor_01", "2k"), ("cobblestone_floor_04", "2k"), ("grassy_cobblestone", "2k")],
        "wall": [("castle_wall_varriation", "2k"), ("rustic_stone_wall", "2k"), ("clay_plaster", "2k"),
                 ("damaged_plaster", "2k"), ("blue_plaster_weathered", "2k")],
        "wood": [("medieval_wood", "2k"), ("brown_planks_05", "1k"), ("dark_wooden_planks", "1k")],
        "roof": [("clay_roof_tiles_02", "2k"), ("roof_slates_02", "2k"), ("grey_roof_tiles", "2k")],
        "terrain": [("aerial_rocks_02", "2k"), ("rock_face", "2k"), ("leafy_grass", "2k"), ("sparse_grass", "2k"),
                    ("snow_02", "1k"), ("brown_mud_rocks_01", "2k"), ("burned_ground_01", "2k"),
                    ("dry_riverbed_rock", "2k"), ("forest_ground_04", "1k"), ("coast_sand_01", "1k")],
    },
    "model": {
        "prop": [("wooden_lantern_01", "1k"), ("wooden_barrels_01", "1k"), ("wooden_crate_01", "1k"),
                 ("barrel_03", "1k"), ("wooden_bucket_01", "1k"), ("wine_barrel_01", "1k"), ("stone_fire_pit", "1k"),
                 ("wooden_ladder", "1k")],
        "nature": [("fir_tree_01", "1k"), ("pine_tree_01", "1k"), ("island_tree_01", "1k"), ("shrub_01", "1k"),
                   ("shrub_02", "1k"), ("shrub_04", "1k"), ("boulder_01", "1k"), ("rock_moss_set_01", "1k"),
                   ("grass_medium_01", "1k"), ("fern_02", "1k"), ("namaqualand_cliff_01", "1k")],
    },
    "hdri": {
        "sky": [("kloofendal_48d_partly_cloudy_puresky", "4k"), ("belfast_sunset_puresky", "4k")],
    },
}


def _get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def catalog():
    p = os.path.join(ROOT, "catalog.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def _save_catalog(c):
    json.dump(c, open(os.path.join(ROOT, "catalog.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def path(aid, key=None):
    """카탈로그 경로. key 없으면 폴더, 텍스처는 'diff'/'nor_gl'/'rough'/'disp'/'arm', 모델은 'gltf', hdri 는 'hdr'."""
    e = catalog()[aid]
    base = os.path.join(ROOT, e["type"], aid)
    return base if key is None else os.path.join(base, e["files"][key])


def fetch(kind, aid, res, category=""):
    c = catalog()
    if aid in c and c[aid]["res"] == res:
        return c[aid]
    files = json.loads(_get(f"{API}/files/{aid}"))
    info = json.loads(_get(f"{API}/info/{aid}"))
    base = os.path.join(ROOT, kind, aid)
    os.makedirs(base, exist_ok=True)
    got, total = {}, 0

    def dl(url, rel):
        nonlocal total
        dst = os.path.join(base, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if not os.path.exists(dst):
            data = _get(url)
            open(dst, "wb").write(data)
        total += os.path.getsize(dst)
        return rel

    if kind == "tex":
        for key in ("diff", "nor_gl", "rough", "disp", "arm", "ao"):
            for k2 in (key, key.capitalize(), {"diff": "Diffuse", "rough": "Rough", "disp": "Displacement", "ao": "AO"}.get(key, key)):
                if k2 in files:
                    r = files[k2].get(res) or files[k2][sorted(files[k2])[0]]
                    f = r.get("jpg") or r.get("png") or r[next(iter(r))]
                    got[key] = dl(f["url"], os.path.basename(f["url"]))
                    break
    elif kind == "model":
        g = files["gltf"].get(res) or files["gltf"][sorted(files["gltf"])[0]]
        g = g["gltf"]
        got["gltf"] = dl(g["url"], os.path.basename(g["url"]))
        for rel, f in g.get("include", {}).items():
            dl(f["url"], rel)
    elif kind == "hdri":
        h = files["hdri"][res]["hdr"]
        got["hdr"] = dl(h["url"], os.path.basename(h["url"]))
    c = catalog()
    c[aid] = {"type": kind, "category": category, "license": "CC0 (Poly Haven)", "source": f"https://polyhaven.com/a/{aid}",
              "res": res, "files": got, "bytes": total, "tags": info.get("tags", []), "name": info.get("name", aid)}
    _save_catalog(c)
    return c[aid]


def fetch_all():
    os.makedirs(ROOT, exist_ok=True)
    for kind, cats in SETS.items():
        for cat, items in cats.items():
            for aid, res in items:
                try:
                    e = fetch(kind, aid, res, cat)
                    print(f"ok  {kind:5} {aid:40} {e['bytes'] / 1e6:6.1f} MB")
                except Exception as ex:  # 이름이 없거나 받기 실패 -> 보고하고 넘어감
                    print(f"ERR {kind:5} {aid:40} {ex}")


if __name__ == "__main__":
    if len(sys.argv) >= 3:
        print(fetch(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "1k"))
    else:
        fetch_all()
