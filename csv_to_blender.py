# ----- Ce code pose les murs à partir d'un csv avec leurs positions -----
import bpy
import csv
import io

def fr_float(s):
    """'0,15' -> 0.15 ; '', None -> None"""
    if s is None:
        return None
    s = str(s).strip().strip('"').strip("'")
    if s == "" or s.lower() in {"nan", "null"}:
        return None
    return float(s.replace(",", "."))

def set_transform(obj, X, Y, Z, cx, cy, cz):
    # Dimensions
    if X is not None and Y is not None and Z is not None:
        obj.dimensions = (max(X, 0.0001), max(Y, 0.0001), max(Z, 0.0001))
    # Location
    if cx is not None and cy is not None and cz is not None:
        obj.location = (cx, cy, cz)

def get_or_create_object(name):
    obj = bpy.data.objects.get(name)
    if obj is None:
        bpy.ops.mesh.primitive_cube_add(location=(0,0,0))
        obj = bpy.context.active_object
        obj.name = name
    return obj


csv_path = bpy.path.abspath("C:\\Users\\totor\\Desktop\\Antiquaire\\programmation\\data\\murs_export.csv")
with open(csv_path, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    updated, created = 0, 0
    for row in reader:
        name = (row.get("Murs") or "").strip()
        if not name:
            continue
        X = fr_float(row.get("X"))
        Y = fr_float(row.get("Y"))
        Z = fr_float(row.get("Z"))
        cx = fr_float(row.get("centre_x")) if "centre_x" in row else 0.0
        cy = fr_float(row.get("centre_y")) if "centre_y" in row else 0.0
        cz = fr_float(row.get("centre_z")) if "centre_z" in row else 0.0

        existed = name in bpy.data.objects
        obj = get_or_create_object(name)
        set_transform(obj, X, Y, Z, cx, cy, cz)
        if existed:
            updated += 1
        else:
            created += 1

print(f"Objets mis à jour : {updated} | créés : {created}")