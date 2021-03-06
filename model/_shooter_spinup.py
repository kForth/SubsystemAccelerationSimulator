from model._custom import CustomModel
from model.motors import Motor


class ShooterSpinupModel(CustomModel):
    def __init__(self,
                 motors: Motor,
                 gear_ratio: float,
                 wheel_diameter: float,
                 wheel_inertia: float,
                 motor_current_limit=None,
                 motor_peak_current_limit=None,
                 motor_voltage_limit=None,
                 k_gearbox_efficiency=0.8,
                 k_resistance_s=0,
                 k_resistance_v=0,
                 battery_voltage=12.5,
                 resistance_com=0.013,
                 resistance_one=0.002,
                 max_dist=1,
                 time_step=0.001,
                 simulation_time=120.0,
                 initial_position=0,
                 initial_velocity=0,
                 initial_acceleration=0,
                 controller=None,
                 auto_calc=True,
                 name=None):

        self.PLOT_FACTORS.update({
            'surface_vel':  1
        })
        self.HEADERS.update({
            'pos':          'Position (rad)',
            'vel':          'Velocity (rad/s)',
            'surface_vel':  'Surface Velocity (m/s)',
            'accel':        'Acceleration (rad/s/s)',
            'error':        'Error (rad)',
            'goal':         'Goal (rad)'
        })
        super().__init__(motors=motors,
                         k_resistance_s=k_resistance_s,
                         k_resistance_v=k_resistance_v,
                         k_gearbox_efficiency=k_gearbox_efficiency,
                         gear_ratio=gear_ratio,
                         effective_diameter=wheel_diameter,
                         effective_mass=wheel_inertia,
                         check_for_slip=False,
                         coeff_kinetic_friction=1,
                         coeff_static_friction=1,
                         battery_voltage=battery_voltage,
                         resistance_com=resistance_com,
                         resistance_one=resistance_one,
                         time_step=time_step,
                         simulation_time=simulation_time,
                         max_dist=max_dist,
                         incline_angle=0,
                         motor_current_limit=motor_current_limit,
                         motor_peak_current_limit=motor_peak_current_limit,
                         motor_voltage_limit=motor_voltage_limit,
                         initial_position=initial_position,
                         initial_velocity=initial_velocity,
                         initial_acceleration=initial_acceleration,
                         controller=controller,
                         auto_calc=auto_calc,
                         name=name)

    def _calc_max_accel(self, velocity):
        motor_speed = velocity * self.gear_ratio

        applied_voltage = min(self._voltage, self._voltage_setpoint)

        self._current_per_motor = (applied_voltage - (motor_speed / self.motors.k_v)) / self.motors.k_r

        if velocity > 0 and self.motor_current_limit is not None:
            self._current_per_motor = min(self._current_per_motor, self.motor_current_limit)

        max_torque_at_voltage = self.motors.k_t * self._current_per_motor

        available_torque_at_pivot = self.k_gearbox_efficiency * max_torque_at_voltage * self.gear_ratio

        tuned_resistance = self.k_resistance_s + self.k_resistance_v * velocity

        net_torque_at_pivot = available_torque_at_pivot - tuned_resistance

        self._voltage = self.battery_voltage - self.num_motors * self._current_per_motor * self.resistance_com - \
                        self._current_per_motor * self.resistance_one  # compute battery drain

        if net_torque_at_pivot < 0:
            net_torque_at_pivot = 0
        return net_torque_at_pivot / self.effective_mass

    def get_info(self):
        return "{0}x{1} @ {2}:1 - {3}m".format(self.motors.__class__.__name__, self.num_motors, self.gear_ratio,
                                                round(self.effective_diameter, 2))

    def _get_data_point(self):
        point = super()._get_data_point()
        point.update({
            'surface_vel':   self._voltage * self.effective_radius
        })
        return point