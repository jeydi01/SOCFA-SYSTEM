# check_wheat.py
import cv2, numpy as np, glob, os

WHEAT_13 = r"C:\Users\facun\Downloads\new dataset\Wheat-dataset\Wheat-dataset\wheat_13082019\RGB"

files = [f for f in glob.glob(f'{WHEAT_13}/*.png') if os.path.getsize(f) > 1000000][:20]
r_vals, g_vals, b_vals = [], [], []
for f in files:
    img = cv2.imread(f)
    if img is None: continue
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    r_vals.append(img[:,:,0].mean())
    g_vals.append(img[:,:,1].mean())
    b_vals.append(img[:,:,2].mean())

print(f"wheat_13082019:")
print(f"  R:{np.mean(r_vals):.1f} G:{np.mean(g_vals):.1f} B:{np.mean(b_vals):.1f}")
print(f"  G-R: {np.mean(g_vals)-np.mean(r_vals):.1f}")