import numpy as np
import pydrake.symbolic as ps
import torch
import time

class PendulumDynamics():
    def __init__(self, dt):
        """
        x = [x pos, y pos, heading, speed, steering_angle]
        u = [acceleration, steering_velocity]
        """
        self.dt = dt
        self.dim_x = 2
        self.dim_u = 1

        """Jacobian computations"""
        self.x_sym = np.array([ps.Variable("x_{}".format(i)) for i in range(self.dim_x)])
        self.u_sym = np.array([ps.Variable("u_{}".format(i)) for i in range(self.dim_u)])
        self.f_sym = self.dynamics_sym(self.x_sym, self.u_sym)

        self.jacobian_xu_sym = ps.Jacobian(
            self.f_sym, np.hstack((self.x_sym, self.u_sym)))
        
    def dynamics_sym(self, x, u):
        """
        Symbolic expression for dynamics. Used to compute
        linearizations of the system.
        x (np.array, dim: n): state
        u (np.array, dim: m): action        
        """
        angle = x[0]
        speed = x[1]

        # Do semi-implicit integration.
        next_speed = speed + self.dt * (-ps.sin(angle) + u[0])
        next_angle = angle + self.dt * next_speed

        x_new = np.array([next_angle, next_speed])
        return x_new


    def dynamics_np(self, x, u):
        """
        Numeric expression for dynamics.
        x (np.array, dim: n): state
        u (np.array, dim: m): action
        """
        angle = x[0]
        speed = x[1]

        # Do semi-implicit integration.
        next_speed = speed + self.dt * (-np.sin(angle) + u[0])
        next_angle = angle + self.dt * next_speed

        x_new = np.array([next_angle, next_speed])
        return x_new

    def dynamics_batch_np(self, x, u):
        """
        Batch dynamics. Uses pytorch for 
        -args:
            x (np.array, dim: B x n): batched state
            u (np.array, dim: B x m): batched input
        -returns:
            xnext (np.array, dim: B x n): batched next state
        """

        angle = x[:,0]
        speed = x[:,1]
        torque = u[:,0]

        # Do semi-implicit integration.
        next_speed = speed + self.dt * (-np.sin(angle) + torque)
        next_angle = angle + self.dt * next_speed

        x_new = np.vstack((next_angle, next_speed)).transpose()
        return x_new


    def dynamics_batch_torch(self, x, u):
        """
        Batch dynamics. Uses pytorch for 
        -args:
            x (np.array, dim: B x n): batched state
            u (np.array, dim: B x m): batched input
        -returns:
            xnext (np.array, dim: B x n): batched next state
        """
        x = torch.Tensor(x).cuda()
        u = torch.Tensor(u).cuda()

        heading = x[:,2]
        v = x[:,3]
        steer = x[:,4]

        dxdt = torch.vstack((
            v * torch.cos(heading),
            v * torch.sin(heading),
            v * torch.tan(steer),
            u[:,0],
            u[:,1]
        )).T
        x_new = x + self.dt * dxdt
        return x_new

    def jacobian_xu(self, x, u):
        """
        Recoever linearized dynamics dfd(xu) as a function of x, u
        """
        env = {self.x_sym[i]: x[i] for i in range(self.dim_x)}
        env.update({self.u_sym[i]: u[i] for i in range(self.dim_u)})
        J_xu = ps.Evaluate(self.jacobian_xu_sym, env)
        return J_xu