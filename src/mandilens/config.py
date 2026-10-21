"""Thresholds and grade bands.

These bands belong to MandiLens. They are not an AGMARK grade and not a
government standard. Change them here if a buyer wants different cutoffs.
"""

# Printed ArUco square. The black square, not the white quiet zone, is this wide.
MARKER_MM = 50.0
MARKER_ID = 0
MARKER_DICT = "DICT_4X4_50"

# Longest side we process. Phone photos get scaled down. The marker sets the scale.
MAX_SIDE_PX = 1600

# Quality gate. Blur is the variance of the Laplacian after a contrast stretch,
# so a dark photo is not punished for being dark.
BLUR_MIN = 80.0
BRIGHT_MIN = 85.0
BRIGHT_MAX = 235.0
GLARE_MAX = 0.015
MASK_FRACTION_MAX = 0.45
# Median Lab chroma of the whole frame. A red or green cloth sits above this.
TRAY_CHROMA_MAX = 46.0
# Warp only when the marker itself is clearly a trapezoid.
# A nearly square marker does not carry a stable homography for the whole frame.
MARKER_SKEW_MAX = 1.18

# Smallest fruit we will grade, in millimetres. Smaller blobs are noise.
MIN_DIAMETER_MM = 22.0

# House grade bands.
SIZE_A_MM = 55.0
SIZE_B_MM = 40.0
DEFECT_A_PCT = 4.0
DEFECT_B_PCT = 12.0

# Shape. A light touch between two fruit should not drop the grade.
# A real bite or a badly broken outline will.
SOLIDITY_DROP = 0.78

# Below this, the agent will not route until a person checks the fruit.
CONFIDENCE_REVIEW = 0.70

# Agent loop cap. Includes inspect steps.
MAX_STEPS = 6

# Upload limit for the local API and the Lambda handlers.
MAX_UPLOAD_BYTES = 8_000_000

# Where a lot goes once it is trusted.
# processing: at least this share of the lot is grade C
# mandi: no grade C, and at least this share is grade A
ROUTE_C_SHARE = 0.30
ROUTE_A_SHARE = 0.60
