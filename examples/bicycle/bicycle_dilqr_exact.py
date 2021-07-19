import numpy as np
import time

from bicycle_dynamics import BicycleDynamics
from dilqr_exact import DiLQR_Exact

import matplotlib.pyplot as plt 
from matplotlib import cm

# 1. Load dynamics.
bicycle = BicycleDynamics(0.1)
dynamics = bicycle.dynamics_np
dynamics_batch = bicycle.dynamics_batch_np
jacobian_xu = bicycle.jacobian_xu

# 2. Set up desried trajectory and cost parameters.
timesteps = 100
Q = np.diag([5, 5, 3, 0.1, 0.1])
Qd = np.diag([50, 50, 30, 1, 1])
R = np.diag([1, 0.1])
x0 = np.array([0, 0, 0, 0, 0])
xd = np.array([3.0, 1.0, np.pi/2, 0, 0])
xdt = np.tile(xd, (timesteps+1,1))
xbound = [
    -np.array([1e4, 1e4, 1e4, 1e4, np.pi/4]),
     np.array([1e4, 1e4, 1e4, 1e4, np.pi/4])
]
ubound = np.array([
    -np.array([1e4, 1e4]),
     np.array([1e4, 1e4])
])

# 3. Set up initial guess.
u_trj = np.tile(np.array([0.1, 0.0]), (timesteps,1))
x_initial_var = np.array([2.0, 2.0, 1.0, 2.0, 0.01])
u_initial_var = np.array([2.0, 1.0])
num_samples = 10000

# Sampling function for variance stepping.
def sampling(xbar, ubar, iter):
    dx = np.random.normal(0.0, (x_initial_var / (iter ** 0.5)),
        size = (num_samples, bicycle.dim_x))
    du = np.random.normal(0.0, (u_initial_var / (iter ** 0.5)),
        size = (num_samples, bicycle.dim_u))        
    return dx, du

# 4. Solve.
sqp_exact = DiLQR_Exact(
    dynamics,
    jacobian_xu,
    Q, Qd, R, x0, xdt, u_trj,
    xbound, ubound)

time_now = time.time()
sqp_exact.iterate(1e-6, 20)
print("Final cost: " + str(sqp_exact.cost))
print("Elapsed time: " + str(time.time() - time_now))

plt.figure()
plt.axis('equal')
colormap = cm.get_cmap("jet")
num_iters = len(sqp_exact.x_trj_lst)
for i in range(num_iters):
    x_trj = sqp_exact.x_trj_lst[i]
    jm = colormap(i/ num_iters)
    plt.plot(x_trj[:,0], x_trj[:,1], color=(jm[0], jm[1], jm[2], i / num_iters))    

plt.show()