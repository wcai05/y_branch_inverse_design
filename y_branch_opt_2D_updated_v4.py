#############################################################################
# Scriptfile: y_branch_opt_2D.py
#
# Description:
# This script sets up and runs the adjoint shape-based optimization for inverse 
# design of the SOI Y-branch in 2D
#
# Steps include:
# 1. Define the base simulation
# 2. Define the optimizable geometry and optimization parameters
# 3. Run optimization
# 4. Save results
#
# Copyright 2019, Lumerical Solutions, Inc.
# Copyright chriskeraly
##############################################################################

import os, sys
sys.path.append("C:\\Program Files\\Lumerical\\v211\\api\\python\\")
import numpy as np
import scipy as sp
import imp
import lumapi
sys.path.append(os.path.dirname(__file__))
from varFDTD_y_branch import y_branch_init_

from lumopt.utilities.wavelengths import Wavelengths
from lumopt.geometries.polygon import FunctionDefinedPolygon
from lumopt.utilities.materials import Material
from lumopt.figures_of_merit.modematch import ModeMatch
from lumopt.optimizers.generic_optimizers import ScipyOptimizers
from lumopt.optimization import Optimization

######## BASE SIMULATION ########
print(os.path.dirname(__file__))
y_branch_base = y_branch_init_

######## DIRECTORY FOR GDS EXPORT #########
example_directory = os.getcwd()

######## SPECTRAL RANGE #########
wavelengths = Wavelengths(start = 1530e-9, stop = 1570e-9, points = 21)

######## DEFINE OPTIMIZABLE GEOMETRY ########
# The class FunctionDefinedPolygon needs a parameterized Polygon (with points ordered
# in a counter-clockwise direction). Here the geometry is defined by 10 parameters defining
# the knots of a spline, and the resulting Polygon has 200 edges, making it quite smooth.

initial_points_x = np.linspace(-1.0e-6, 1.0e-6, 20)
initial_points_y = np.linspace(0.25e-6, 0.6e-6, initial_points_x.size)
initial_x1_size = int(initial_points_x.size / 4)
initial_points_x1 = np.linspace(1.0e-6,1.2e-6,initial_x1_size)
initial_points_y1 = np.linspace(0.1e-6,0.0e-6,initial_points_x1.size)
def splitter(params):
    points_x = np.concatenate(([initial_points_x.min() - 0.01e-6], initial_points_x, [initial_points_x.max() + 0.01e-6]))
    points_y = np.concatenate(([initial_points_y.min()], params[0:initial_points_x.size], [initial_points_y.max()])) 
    points_x1 = np.concatenate(([initial_points_x1.min() - 0.01e-6], initial_points_x1,[initial_points_x1.max()+ 0.01e-6]))
    points_y1 = np.concatenate(([initial_points_y1.max()], params[initial_points_x.size:], [initial_points_y1.min()]))
    n_interpolation_points = 100
    polygon_points_x = np.linspace(min(points_x), max(points_x), n_interpolation_points)
    polygon_points_x1 = np.linspace(min(points_x1), max(points_x1), int(n_interpolation_points/4))
    interpolator = sp.interpolate.interp1d(points_x, points_y, kind = 'cubic')
    interpolator1 = sp.interpolate.interp1d(points_x1, points_y1, kind = 'cubic')
    polygon_points_y = interpolator(polygon_points_x)
    polygon_points_y1 = interpolator1(polygon_points_x1)
    polygon_points_up = [(x, y) for x, y in zip(polygon_points_x, polygon_points_y)]
    polygon_points_up1 = [(x,y) for x, y in zip(polygon_points_x1, polygon_points_y1)]
    polygon_points_down = [(x, -y) for x, y in zip(polygon_points_x, polygon_points_y)]
    polygon_points_down1 = [(x, -y) for x, y in zip(polygon_points_x1, polygon_points_y1)]
    polygon_points = np.array(polygon_points_up1[::-1] + polygon_points_up[::-1] + polygon_points_down + polygon_points_down1)
    return polygon_points
initial_params = np.concatenate((initial_points_y,initial_points_y1))
bounds = [(0.2e-6, 0.8e-6)] * initial_points_y.size
bounds1 =[(0.,0.06e-6)] * initial_points_y1.size
eps_in = Material(name = 'Si: non-dispersive', mesh_order = 2)
eps_out = Material(name = 'SiO2: non-dispersive', mesh_order = 3)
depth = 220.0e-9
polygon = FunctionDefinedPolygon(func = splitter,
                                 initial_params = initial_params,
                                 bounds = bounds + bounds1,
                                 z = 0.0,
                                 depth = depth,
                                 eps_out = eps_out,
                                 eps_in = eps_in,
                                 edge_precision = 5,
                                 dx = 1.0e-9)

######## FIGURE OF MERIT ########
fom = ModeMatch(monitor_name = 'fom',
                mode_number = 'fundamental mode',
                direction = 'Forward',
                target_T_fwd = lambda wl: np.ones(wl.size),
                norm_p = 1)

######## OPTIMIZATION ALGORITHM ########
scaling_factor = 1.0e6
optimizer = ScipyOptimizers(max_iter = 70,
                            method = 'L-BFGS-B',
                            scaling_factor = scaling_factor,
                            pgtol = 1.0e-5,
                            ftol = 1.0e-5,
                            #target_fom = 0.0,
                            scale_initial_gradient_to = 0.0)

######## PUT EVERYTHING TOGETHER ########
opt = Optimization(base_script = y_branch_base,
                   wavelengths = wavelengths,
                   fom = fom,
                   geometry = polygon,
                   optimizer = optimizer,
                   use_var_fdtd = True,
                   hide_fdtd_cad = True,
                   use_deps = True,
                   plot_history = True,
                   store_all_simulations = False)

######## RUN THE OPTIMIZATION ########
results = opt.run()

######## SAVE THE BEST PARAMETERS TO FILE ########
np.savetxt('../2D_parameters.txt', results[1])

######## EXPORT OPTIMIZED STRUCTURE TO GDS ########
gds_export_script = str("gds_filename = 'y_branch_2D.gds';" +
                        "top_cell = 'model';" +
                        "layer_def = [1, {0}, {1}];".format(-depth/2, depth/2) +
                        "n_circle = 64;" +
                        "n_ring = 64;" +
                        "n_custom = 64;" +
                        "n_wg = 64;" +
                        "round_to_nm = 1;" +
                        "grid = 1e-9;" +
                        "max_objects = 10000;" +
                        "Lumerical_GDS_auto_export;")

with lumapi.MODE(hide = False) as mode:
    mode.cd(example_directory)
    y_branch_init_(mode)         
    mode.addpoly(vertices = splitter(results[1]))
    mode.set('x', 0.0)
    mode.set('y', 0.0)
    mode.set('z', 0.0)
    mode.set('z span', depth)
    mode.set('material','Si: non-dispersive')
    mode.save("y_branch_2D_FINAL")
    mode.eval(gds_export_script)
