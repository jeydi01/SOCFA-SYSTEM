import glob
import numpy as np
from PIL import Image
import os

SESSION_01 = r"C:\Users\facun\Downloads\Component 1 - part 1-2\Component 1 - part 1-2\flight_session_01\flight_session_01"
SESSION_02 = r"C:\Users\facun\Downloads\Component 1 - part 1-2\Component 1 - part 1-2\flight_session_02\filght_session_02"

all_ndvi = []

for session, base in [('Session 01', SESSION_01), ('Session 02', SESSION_02)]:
    files = glob.glob(os.path.join(base, '*', '*FPLAN', '*3.TIF'))[:100]
    ndvi_vals = []
    for red_path in files:
        nir_path = red_path[:-5] + '5.TIF'
        if not os.path.exists(nir_path):
            continue
        try:
            red = np.array(Image.open(red_path)).astype(np.float32)
            nir = np.array(Image.open(nir_path)).astype(np.float32)
            ndvi = (nir - red) / (nir + red + 1e-8)
            ndvi_vals.append(float(np.mean(ndvi)))
        except:
            pass
    print(f"{session}: min={min(ndvi_vals):.4f} max={max(ndvi_vals):.4f} mean={np.mean(ndvi_vals):.4f}")
    all_ndvi.extend(ndvi_vals)

all_ndvi.sort()
print(f"\nOverall: min={min(all_ndvi):.4f} max={max(all_ndvi):.4f} mean={np.mean(all_ndvi):.4f}")

# Show distribution in thirds
third = len(all_ndvi) // 3
print(f"\nBottom third (poor):    {all_ndvi[0]:.4f} to {all_ndvi[third]:.4f}")
print(f"Middle third (moderate): {all_ndvi[third]:.4f} to {all_ndvi[third*2]:.4f}")
print(f"Top third (healthy):     {all_ndvi[third*2]:.4f} to {all_ndvi[-1]:.4f}") 