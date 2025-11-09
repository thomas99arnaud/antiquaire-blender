# ====== Pose les murs + hiérarchie + étiquettes Texte debout (rangées dans leur pièce) ======
import bpy
import csv
import math

# ---------- ID murs: A B C D ----------
def parse_mur_id(mid: str):
    if not isinstance(mid, str) or len(mid) < 4:
        raise ValueError(f"ID mur invalide: {mid!r}")
    A = mid[0]           # étage (1 char, chiffre)
    C = mid[-2]          # orientation X/Y/Z
    D = mid[-1]          # index 0/1
    B = mid[1:-2]        # pièce (1–2 chars)
    if not A.isdigit():  raise ValueError(f"Étages doit être un chiffre: {mid!r}")
    if C not in "XYZ":   raise ValueError(f"Orientation invalide: {mid!r}")
    if D not in "01":    raise ValueError(f"Index invalide: {mid!r}")
    if not (1 <= len(B) <= 2):
        raise ValueError(f"Pièce doit faire 1 ou 2 caractères: {mid!r}")
    return A, B, C, D

# ---------- Collections (strictes & exclusives) ----------
def find_child_collection(parent: bpy.types.Collection, name: str):
    for c in parent.children:
        if c.name == name:
            return c
    return None

def make_child_collection(parent: bpy.types.Collection, name: str) -> bpy.types.Collection:
    coll = find_child_collection(parent, name)
    if coll:
        return coll
    coll = bpy.data.collections.new(name)
    parent.children.link(coll)
    return coll

def iter_descendant_collections(root: bpy.types.Collection):
    stack = list(root.children)
    while stack:
        c = stack.pop()
        yield c
        stack.extend(c.children)

def move_object_exclusive_under(root: bpy.types.Collection,
                                obj: bpy.types.Object,
                                target: bpy.types.Collection):
    """Retire obj de TOUTES les collections sous 'root', puis le lie uniquement à 'target'."""
    for c in iter_descendant_collections(root):
        if obj.name in (o.name for o in c.objects):
            try:
                c.objects.unlink(obj)
            except RuntimeError:
                pass
    if obj.name not in (o.name for o in target.objects):
        target.objects.link(obj)
    scn_root = bpy.context.scene.collection
    if obj.name in (o.name for o in scn_root.objects) and target != scn_root:
        try:
            scn_root.objects.unlink(obj)
        except RuntimeError:
            pass

# ---------- Numérique & objets ----------
def fr_float(s):
    if s is None:
        return None
    s = str(s).strip().strip('"').strip("'")
    if s == "" or s.lower() in {"nan", "null"}:
        return None
    return float(s.replace(",", "."))

def set_transform(obj, X, Y, Z, cx, cy, cz):
    # Dimensions (évite 0)
    if X is not None and Y is not None and Z is not None:
        obj.dimensions = (max(X, 1e-4), max(Y, 1e-4), max(Z, 1e-4))
    # Position
    if cx is not None and cy is not None and cz is not None:
        obj.location = (cx, cy, cz)

def get_or_create_object(name: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
        obj = bpy.context.active_object
        obj.name = name
    return obj

def ensure_emission_mat(name="Label_Emission", strength=3.0):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        nt = mat.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial")
        emis = nt.nodes.new("ShaderNodeEmission")
        emis.inputs["Strength"].default_value = strength
        nt.links.new(emis.outputs["Emission"], out.inputs["Surface"])
    return mat

def get_or_make_child_collection(parent: bpy.types.Collection, name: str) -> bpy.types.Collection:
    coll = find_child_collection(parent, name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        parent.children.link(coll)
    return coll

# ---------- Chemins CSV ----------
csv_path = bpy.path.abspath(r"C:\Users\totor\Desktop\Antiquaire\programmation\data\murs_export.csv")
labels_csv_path = bpy.path.abspath(r"C:\Users\totor\Desktop\Antiquaire\programmation\data\labels.csv")

# ---------- Racine "Bâtiment" ----------
root = find_child_collection(bpy.context.scene.collection, "Bâtiment")
if root is None:
    root = make_child_collection(bpy.context.scene.collection, "Bâtiment")

# ---------- Import murs + hiérarchie ----------
updated, created = 0, 0
with open(csv_path, "r", encoding="utf-8", newline="") as f:
    reader = csv.DictReader(f)
    for row in reader:
        name = (row.get("Murs") or "").strip()
        if not name:
            continue

        try:
            etage, piece, orient, idx = parse_mur_id(name)
        except ValueError as e:
            print(f"⚠️ ID ignoré: {e}")
            continue

        X  = fr_float(row.get("X"))
        Y  = fr_float(row.get("Y"))
        Z  = fr_float(row.get("Z"))
        cx = fr_float(row.get("centre_x")) if "centre_x" in row else None
        cy = fr_float(row.get("centre_y")) if "centre_y" in row else None
        cz = fr_float(row.get("centre_z")) if "centre_z" in row else None

        obj = get_or_create_object(name)
        existed = obj is not None
        set_transform(obj, X, Y, Z, cx, cy, cz)

        # Hiérarchie stricte: Bâtiment / Etage_A / Piece_A_<piece>
        floor_coll = find_child_collection(root, f"Etage_{etage}") or make_child_collection(root, f"Etage_{etage}")
        piece_coll = find_child_collection(floor_coll, f"Piece_{etage}_{piece}") or make_child_collection(floor_coll, f"Piece_{etage}_{piece}")
        move_object_exclusive_under(root, obj, piece_coll)

        if existed and name in bpy.data.objects:
            updated += 1
        else:
            created += 1

print(f"Objets mis à jour : {updated} | créés : {created}")
print("✅ Organisation : Bâtiment / Etage_<A> / Piece_<A>_<B>")

# ---------- Construire les rectangles intérieurs des pièces (pour ranger les étiquettes) ----------
def build_piece_rects():
    """
    Retourne un dict:
      key = f"{A}{B}" (ex '0A', '1AA')
      value = {
        'rect': (xmin, xmax, ymin, ymax),
        'zmin': z_sol,                # altitude du sol de la pièce
        'zmax': z_sol + hauteur,      # plafond (~ hauteur mur X0)
        'etage': A, 'piece': B,
        'collection': Collection Piece_A_B si trouvée
      }
    Hypothèses:
      - murs Y: plan vertical à x = location.x ; épaisseur sur X = dimensions.x
      - murs X: plan horizontal à y = location.y ; épaisseur sur Y = dimensions.y
      - hauteur = dimensions.z du mur X0
    """
    rects = {}
    tmp = {}

    # Indexer murs par pièce
    for obj in bpy.data.objects:
        if obj.type != 'MESH':
            continue
        name = obj.name
        try:
            A, B, C, D = parse_mur_id(name)
        except Exception:
            continue

        key = f"{A}{B}"
        entry = tmp.setdefault(key, {'X': [], 'Y': [], 'anyX0': None})
        if C == 'Y':
            entry['Y'].append((obj.location.x, obj.dimensions.x))
        elif C == 'X':
            entry['X'].append((obj.location.y, obj.dimensions.y))
            if D == '0' and entry['anyX0'] is None:
                entry['anyX0'] = obj  # mur de référence pour le Z

    # Calculer bornes + Z
    for key, axes in tmp.items():
        ys = sorted(axes['Y'], key=lambda t: t[0])  # par x
        xs = sorted(axes['X'], key=lambda t: t[0])  # par y
        if len(ys) < 2 or len(xs) < 2:
            continue

        # bornes intérieures
        x_left  = ys[0][0] + (ys[0][1] * 0.5)
        x_right = ys[-1][0] - (ys[-1][1] * 0.5)
        y_bottom = xs[0][0] + (xs[0][1] * 0.5)
        y_top    = xs[-1][0] - (xs[-1][1] * 0.5)

        # Z : sol = centre_z - hauteur/2 à partir de X0
        ref = axes['anyX0']
        if ref is None:
            # fallback: prendre n'importe quel mur X
            ref = bpy.data.objects.get(key + "X0") or bpy.data.objects.get(key + "X1")
        if ref is None:
            continue
        z_sol = ref.location.z - 0.5 * ref.dimensions.z
        z_max = z_sol + ref.dimensions.z

        A = key[0]
        B = key[1:]
        floor_coll = find_child_collection(root, f"Etage_{A}")
        piece_coll = find_child_collection(floor_coll, f"Piece_{A}_{B}") if floor_coll else None

        rects[key] = {
            'rect': (x_left, x_right, y_bottom, y_top),
            'zmin': z_sol,
            'zmax': z_max,
            'etage': A,
            'piece': B,
            'collection': piece_coll
        }
    return rects


def find_piece_for_point(rects, x, y, z, z_tol=0.05):
    """
    Cherche la pièce dont le rectangle XY contient (x,y)
    ET dont l'altitude [zmin - tol, zmax + tol] contient z.
    Renvoie (key, data) ou (None, None).
    """
    for key, data in rects.items():
        xmin, xmax, ymin, ymax = data['rect']
        if (xmin <= x <= xmax) and (ymin <= y <= ymax):
            if (data['zmin'] - z_tol) <= z <= (data['zmax'] + z_tol):
                return key, data
    return None, None

piece_rects = build_piece_rects()

# ---------- Étiquettes : création de textes debout depuis labels.csv ----------
def create_or_update_text(name: str, texte: str, cx: float, cy: float, cz: float,
                          size=0.6, emission=True) -> bpy.types.Object:
    """Crée/MAJ un objet Texte debout nommé `name` à (cx,cy,cz)."""
    obj = bpy.data.objects.get(name)
    if obj is None:
        bpy.ops.object.text_add(location=(cx, cy, cz))
        obj = bpy.context.active_object
        obj.name = name
    else:
        obj.location = (cx, cy, cz)

    # Contenu
    obj.data.body = str(texte)

    # Debout (pas couché)
    obj.rotation_euler = (0.0, 0.0, 0.0)

    # Centrage + taille
    obj.data.align_x = 'CENTER'
    obj.data.align_y = 'CENTER'
    obj.data.size = float(size) if size else 0.6
    obj.data.extrude = 0.0
    obj.data.bevel_depth = 0.0

    # Matériau émissif (lisible)
    if emission:
        mat = ensure_emission_mat()
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)

    return obj

# Fallback si aucune pièce trouvée
labels_fallback = get_or_make_child_collection(root, "Etiquettes")

try:
    with open(labels_csv_path, "r", encoding="utf-8", newline="") as lf:
        lreader = csv.DictReader(lf)
        count_new, count_upd = 0, 0
        idx = 0
        for row in lreader:
            texte = (row.get("texte") or "").strip()
            cx = fr_float(row.get("centre_x"))
            cy = fr_float(row.get("centre_y"))
            cz = fr_float(row.get("centre_z"))

            if not texte or cx is None or cy is None or cz is None:
                continue

            name = f"TXT_{idx:03d}"
            idx += 1

            existed_before = name in bpy.data.objects
            obj = create_or_update_text(name, texte, cx, cy, cz, size=0.6, emission=True)

            # Trouver la pièce qui contient (cx, cy) et ranger l'étiquette dedans
            piece_key, pdata = find_piece_for_point(piece_rects, cx, cy, cz)
            if pdata and pdata['collection'] is not None:
                move_object_exclusive_under(root, obj, pdata['collection'])
            else:
                # fallback "Bâtiment / Etiquettes" (inchangé)
                if obj.name not in (o.name for o in labels_fallback.objects):
                    labels_fallback.objects.link(obj)
                scn_root = bpy.context.scene.collection
                if obj.name in (o.name for o in scn_root.objects):
                    try:
                        scn_root.objects.unlink(obj)
                    except RuntimeError:
                        pass


            if existed_before:
                count_upd += 1
            else:
                count_new += 1

    print(f"✅ Étiquettes: créées {count_new}, mises à jour {count_upd} (source: {labels_csv_path})")
    print("✅ Les étiquettes sont rangées dans la collection de leur pièce quand elle est identifiée.")
except FileNotFoundError:
    print(f"ℹ️ Fichier d'étiquettes introuvable : {labels_csv_path}")
