%
(JIG-45 A — 3D demo, G0/G1 only)
G21 G90 G17
G54
G0  Z15
G0  X0 Y0
S12000 M3
F800

(Go to start, surface touch)
G0  X10 Y10
G1  Z0    F300

(Depth 1 @ Z=0: rectangle 60x30 from (10,10) to (70,40))
G1  X70 Y10  F800
G1  X70 Y40
G1  X10 Y40
G1  X10 Y10

(Depth 2 @ Z=-1.5)
G1  Z-1.5  F300
G1  X70 Y10  F800
G1  X70 Y40
G1  X10 Y40
G1  X10 Y10

(Depth 3 @ Z=-3.0)
G1  Z-3.0  F300
G1  X70 Y10  F800
G1  X70 Y40
G1  X10 Y40
G1  X10 Y10

(Ramp up and out in 3D so you see sloped lines)
G1  X70 Y25 Z-2.0
G1  X70 Y45 Z-1.0
G1  X50 Y45 Z0.0

(Exit)
G0  Z15
M5
G0  X0 Y0
M30
%