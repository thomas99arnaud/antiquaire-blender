# ----- Pose les murs et organise en Collections: Bâtiment / Etage_A / Piece_A_B -----
import bpy
import csv

# ---------- parse ID: A B C D ----------
def parse_mur_id(mid: str):
    if not isinstance(mid, str) or len(mid) < 4:
        raise ValueError(f"ID mur invalide: {mid!r}")
    A = mid[0]           # étage (1 char)
    C = mid[-2]          # orientation
    D = mid[-1]          # index
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
    """Toujours créer une nouvelle Collection et la lier sous parent (pas de réutilisation globale)."""
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
    """Retire obj de toutes les collections descendantes de 'root', puis le lie à 'target'."""
    # Unlink partout sous la hiérarchie Bâtiment
    for c in iter_descendant_collections(root):
        if obj.name in (o.name for o in c.objects):
            try:
                c.objects.unlink(obj)
            except RuntimeError:
                pass
    # Link dans la cible
    if obj.name not in (o.name for o in target.objects):
        target.objects.link(obj)
    # Optionnel: l’enlever de la collection de scène
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
    if X is not None and Y is not None and Z is not None:
        obj.dimensions = (max(X, 1e-4), max(Y, 1e-4), max(Z, 1e-4))
    if cx is not None and cy is not None and cz is not None:
        obj.location = (cx, cy, cz)

def get_or_create_object(name: str) -> bpy.types.Object:
    obj = bpy.data.objects.get(name)
    if obj is None:
        bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0))
        obj = bpy.context.active_object
        obj.name = name
    return obj

# ---------- Lecture + placement + hiérarchie ----------
csv_path = bpy.path.abspath("C:\\Users\\totor\\Desktop\\Antiquaire\\programmation\\data\\murs_export.csv")

# Racine du bâtiment (unique)
root = find_child_collection(bpy.context.scene.collection, "Bâtiment")
if root is None:
    root = make_child_collection(bpy.context.scene.collection, "Bâtiment")

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
        existed = True if obj else False
        set_transform(obj, X, Y, Z, cx, cy, cz)

        # Hiérarchie stricte: Etage_A / Piece_A_<piece>
        floor_coll = find_child_collection(root, f"Etage_{etage}") or make_child_collection(root, f"Etage_{etage}")
        piece_coll = find_child_collection(floor_coll, f"Piece_{etage}_{piece}") or make_child_collection(floor_coll, f"Piece_{etage}_{piece}")

        # Déplacement exclusif : l’objet n’appartient qu’à cette pièce sous ce bâtiment
        move_object_exclusive_under(root, obj, piece_coll)

        if name in bpy.data.objects:
            updated += 1
        else:
            created += 1

print(f"Objets mis à jour : {updated} | créés : {created}")
print("✅ Organisation stricte : Bâtiment / Etage_<A> / Piece_<A>_<B> (A=étage, B=pièce)")
