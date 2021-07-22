from typing import Dict

import numpy as np
from pydrake.all import ModelInstanceIndex
from quasistatic_simulator.core.quasistatic_simulator import (
    QuasistaticSimulator)


class QuasistaticDynamics:
    def __init__(self, h: float, q_sim: QuasistaticSimulator):
        self.h = h
        self.q_sim = q_sim

        self.dim_x = q_sim.plant.num_positions()
        self.dim_u = q_sim.num_actuated_dof()

        self.position_indices_dict = dict()
        for model in q_sim.models_all:
            self.position_indices_dict[model] = \
                q_sim.get_position_indices_for_model(model)

    def get_u_indices_into_x(self):
        u_indices = np.zeros(self.dim_u, dtype=int)
        i_start = 0
        for model in self.q_sim.models_actuated:
            indices = self.q_sim.velocity_indices_dict[model]
            n_a_i = len(indices)
            u_indices[i_start: i_start + n_a_i] = indices
            i_start += n_a_i
        return u_indices

    def get_q_a_cmd_dict_from_u(self, u: np.ndarray):
        q_a_cmd_dict = dict()
        i_start = 0
        for model in self.q_sim.models_actuated:
            n_a_i = self.q_sim.n_v_dict[model]
            q_a_cmd_dict[model] = u[i_start: i_start + n_a_i]
            i_start += n_a_i

        return q_a_cmd_dict

    def get_q_dict_from_x(self, x: np.ndarray):
        q_dict = {
            model: x[n_q_indices]
            for model, n_q_indices in self.position_indices_dict.items()}

        return q_dict

    def get_x_from_q_dict(self, q_dict: Dict[ModelInstanceIndex, np.ndarray]):
        x = np.zeros(self.dim_x)
        for model, n_q_indices in self.position_indices_dict.items():
            x[n_q_indices] = q_dict[model]

        return x

    def get_u_from_q_cmd_dict(self,
                              q_cmd_dict: Dict[ModelInstanceIndex, np.ndarray]):
        u = np.zeros(self.dim_u)
        i_start = 0
        for model in self.q_sim.models_actuated:
            n_v_i = self.q_sim.n_v_dict[model]
            u[i_start: i_start + n_v_i] = q_cmd_dict[model]
            i_start += n_v_i

        return u

    def get_Q_from_Q_dict(self,
                          Q_dict: Dict[ModelInstanceIndex, np.ndarray]):
        Q = np.eye(self.dim_x)
        for model, idx in self.q_sim.velocity_indices_dict.items():
            Q[idx, idx] = Q_dict[model]
        return Q


    def dynamics(self, x: np.ndarray, u: np.ndarray,
                 mode: str = 'qp_mp', requires_grad: bool = False):
        """
        :param x: the position vector of self.q_sim.plant.
        :param u: commanded positions of models in
            self.q_sim.models_actuated, concatenated into one vector.
        """
        q_dict = self.get_q_dict_from_x(x)
        q_a_cmd_dict = self.get_q_a_cmd_dict_from_u(u)
        tau_ext_u_dict = self.q_sim.calc_gravity_for_unactuated_models()
        tau_ext_a_dict = \
            self.q_sim.get_generalized_force_from_external_spatial_force([])
        tau_ext_dict = {**tau_ext_a_dict, **tau_ext_u_dict}

        self.q_sim.update_configuration(q_dict)
        q_next_dict = self.q_sim.step(
            q_a_cmd_dict, tau_ext_dict, self.h,
            mode=mode, requires_grad=requires_grad)

        return self.get_x_from_q_dict(q_next_dict)

    def dynamics_batch(self, x, u):
        """
        Batch dynamics. Uses pytorch for
        -args:
            x (np.array, dim: B x n): batched state
            u (np.array, dim: B x m): batched input
        -returns:
            x_next (np.array, dim: B x n): batched next state
        """
        n_batch = x.shape[0]
        x_next = np.zeros((n_batch, self.dim_x))

        for i in range(n_batch):
            x_next[i] = self.dynamics(x[i], u[i])
        return x_next

    def publish_trajectory(self, x_traj):
        q_dict_traj = [self.get_q_dict_from_x(x) for x in x_traj]
        self.q_sim.animate_system_trajectory(h=self.h, q_dict_traj=q_dict_traj)