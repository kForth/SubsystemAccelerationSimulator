from collections import OrderedDict
from math import radians, sin, cos

from controllers.fixed_voltage import FixedVoltageController


class CustomModel:
    BROWNOUT_VOLTAGE = 7

    HEADERS = {
        'time':          'Time (s)',
        'pos':           'Position (m)',
        'vel':           'Velocity (m/s)',
        'accel':         'Acceleration (m/s/s)',
        'voltage':       'Voltage (V)',
        'current':       'Current/10 (A)',
        'total_current': 'Total Current/100 (A)',
        'sys_voltage':   'System Voltage (V)',
        'energy':        'Energy (nAh)',
        'total_energy':  'Total Energy/10 (mAh)',
        'slipping':      'Slipping',
        'brownout':      'Brownout',
        'gravity':       'Force of Gravity (N)',
        'error':         'Error (m)',
        'goal':          'Goal (m)',
        'done':          'Done'
    }

    PLOT_FACTORS = {
        'time':          1,
        'pos':           1,
        'vel':           1,
        'accel':         1,
        'voltage':       1,
        'current':       10,
        'total_current': 100,
        'sys_voltage':   1,
        'energy':        100,
        'total_energy':  10,
        'slipping':      1,
        'brownout':      1,
        'gravity':       1,
        'error':         1,
        'goal':          1,
        'done':          1
    }

    def __init__(self,
                 motors,  # Motor object
                 gear_ratio,  # Gear ratio, driven/driving
                 motor_current_limit,  # Current limit per motor, A
                 motor_peak_current_limit,  # Peak Current limit per motor, A
                 motor_voltage_limit,  # Voltage limit per motor, V
                 effective_diameter,  # Effective diameter, m
                 effective_mass,  # Effective mass, kg
                 k_gearbox_efficiency,  # Gearbox efficiency fraction
                 incline_angle,  # Incline angle relative to ground, deg
                 check_for_slip,  # Check for slip or not
                 coeff_kinetic_friction,  # µk
                 coeff_static_friction,  # µs
                 k_resistance_s,  # static resistance, N
                 k_resistance_v,  # viscous resistance, N/(ft/s)
                 battery_voltage,  # Fully-charged open-circuit battery voltage
                 resistance_com,  # Resistance from bat to PDB (incl main breaker, Ω
                 resistance_one,  # Resistance from PDB to motor (incl PDB breaker), Ω
                 time_step=0.01,  # Integration step size, s
                 simulation_time=20,  # Integration duration, s
                 max_dist=5,  # Max distance to integrate to, m
                 initial_position=0,  # Initial position to start simulation from, m
                 initial_velocity=0,  # Initial velocity to start simulation from, m/s
                 initial_acceleration=0,  # Initial acceleration to start simulation from, m/s/s
                 controller=None,
                 auto_calc=True,
                 name=None):

        self.motors = motors
        self.num_motors = self.motors.num_motors
        self.k_resistance_s = k_resistance_s
        self.k_resistance_v = k_resistance_v
        self.k_gearbox_efficiency = k_gearbox_efficiency
        self.gear_ratio = gear_ratio
        self.effective_diameter = effective_diameter
        self.incline_angle = incline_angle
        self.effective_mass = effective_mass
        self.check_for_slip = check_for_slip
        self.coeff_kinetic_friction = coeff_kinetic_friction
        self.coeff_static_friction = coeff_static_friction
        self.motor_current_limit = motor_current_limit
        self.motor_peak_current_limit = motor_peak_current_limit
        self.motor_voltage_limit = motor_voltage_limit
        self.battery_voltage = battery_voltage
        self.resistance_com = resistance_com
        self.resistance_one = resistance_one
        self.time_step = time_step
        self.simulation_time = simulation_time
        self.max_dist = max_dist
        self.initial_position = initial_position
        self.initial_velocity = initial_velocity
        self.initial_acceleration = initial_acceleration
        self.name = name
        self.controller = controller
        if self.controller is None:
            self.controller = FixedVoltageController()
            self.controller.set_gains(
                    self.motor_voltage_limit if motor_voltage_limit is not None else self.battery_voltage)

        # Calculate derived constants
        self.effective_radius = effective_diameter / 2
        self.effective_weight = self.effective_mass * 9.80665  # effective weight, Newtons

        self.traction_limited = ((self.motor_current_limit if self.motor_current_limit is not None
                                  else self.motors.stall_current) *
                                 self.motors.k_t * self.gear_ratio * self.k_gearbox_efficiency /
                                 self.effective_radius) > (self.effective_weight * self.coeff_static_friction)
        if self.check_for_slip:
            print(self.name)
            print('\tTraction Limited: \t{}'.format(self.traction_limited))
        if self.incline_angle > 0:
            print(self.incline_angle)
            print('\tHold Current: \t{}A'.format(
                    round(self._get_gravity_force() * self.effective_radius / self.gear_ratio / self.motors.k_t), 1))  # N * m / (N*m/A)

        self.init_sim_vars()
        if auto_calc:
            self.calc()

    def init_sim_vars(self):
        self._time = 0  # elapsed time, seconds
        self._position = self.initial_position  # distance traveled, meters
        self._velocity = self.initial_velocity  # speed, meters/sec
        self._acceleration = self.initial_acceleration  # acceleration, meters/sec/sec
        self._voltage = self.battery_voltage  # Voltage at the motor
        self._current_per_motor = 0  # current per motor, amps
        self._energy_per_motor = 0  # power used, mAh
        self._cumulative_energy = 0  # total power used mAh
        self._slipping = False
        self._brownout = False
        self._voltage_setpoint = 0

        self._current_history_size = 20
        self._current_history = [0 for _ in range(self._current_history_size)]
        self._was_current_limited = False

        self.data_points = []

    def _get_gravity_force(self):
        return self.effective_weight * sin(radians(self.incline_angle))

    def _get_normal_force(self):
        return self.effective_weight * cos(radians(self.incline_angle))

    def update(self):
        self._voltage_setpoint = self.controller.update(self._position)
        if self.motor_voltage_limit is not None:
            self._voltage_setpoint = min(self.motor_voltage_limit,
                                         max(-self.motor_voltage_limit, self._voltage_setpoint))

    def _calc_max_accel(self, velocity):
        motor_speed = velocity / self.effective_radius * self.gear_ratio

        available_voltage = self._voltage
        if self.motor_voltage_limit:
            available_voltage = min(self._voltage, self.motor_voltage_limit)
        applied_voltage = min(self._voltage_setpoint, available_voltage)

        self._current_per_motor = (applied_voltage - (motor_speed / self.motors.k_v)) / self.motors.k_r

        if velocity > 0 and self.motor_current_limit is not None:
            if (sum(self._current_history) / len(self._current_history)) \
                    > self.motor_current_limit or self._was_current_limited:
                self._was_current_limited = True
                self._current_per_motor = min(self._current_per_motor, self.motor_current_limit)
        if self.motor_peak_current_limit is not None:
            self._current_per_motor = min(self._current_per_motor, self.motor_peak_current_limit)

        max_torque_at_voltage = self.motors.k_t * self._current_per_motor

        available_torque_at_axle = self.k_gearbox_efficiency * max_torque_at_voltage * self.gear_ratio
        available_force_at_axle = available_torque_at_axle / self.effective_radius

        if self.check_for_slip:
            if available_force_at_axle > self._get_normal_force() * self.coeff_static_friction:
                self._slipping = True
            elif available_force_at_axle < self._get_normal_force() * self.coeff_kinetic_friction:
                self._slipping = False

            if self._slipping:
                available_force_at_axle = (self._get_normal_force() * self.coeff_kinetic_friction)

        self._voltage = self.battery_voltage - (self._current_per_motor * self.resistance_one) - \
                        (self.num_motors * self._current_per_motor * self.resistance_com)

        self._brownout = self._voltage < self.BROWNOUT_VOLTAGE

        tuned_resistance = self.k_resistance_s + self.k_resistance_v * velocity  # rolling resistance, N
        net_accel_force = available_force_at_axle - tuned_resistance - self._get_gravity_force()  # Net force, N

        if net_accel_force < 0 and self._position <= 0:
            net_accel_force = 0
        return net_accel_force / self.effective_mass

    def _integrate_with_heun(self):  # numerical integration using Heun's Method
        self._time = self.time_step
        while self._time < self.simulation_time + self.time_step and \
                (self._position < self.max_dist or not self.max_dist):
            self.update()
            v_temp = self._velocity + self._acceleration * self.time_step  # kickstart with Euler step
            a_temp = self._calc_max_accel(v_temp)
            v_temp = self._velocity + (self._acceleration + a_temp) / 2 * \
                                      self.time_step  # recalc v_temp trapezoidally
            self._position += (self._velocity + v_temp) / 2 * self.time_step  # update x trapezoidally
            self._velocity = v_temp  # update V
            self._acceleration = self._calc_max_accel(v_temp)  # update a

            self._energy_per_motor = self._current_per_motor * self.time_step * 1000 / 60 / 60  # calc power usage in mAh
            self._cumulative_energy += self._energy_per_motor * self.num_motors
            self._current_history.append(self._current_per_motor)
            if len(self._current_history) > self._current_history_size:
                self._current_history = self._current_history[-self._current_history_size:]

            self._add_data_point()
            self._time += self.time_step

    def _get_data_point(self):
        point = OrderedDict({
            'time':          self._time,
            'pos':           self._position,
            'vel':           self._velocity,
            'accel':         self._acceleration,
            'voltage':       self._voltage_setpoint,
            'current':       self._current_per_motor,
            'total_current': self._current_per_motor * self.num_motors,
            'sys_voltage':   self._voltage,
            'energy':        self._energy_per_motor,
            'total_energy':  self._cumulative_energy,
            'slipping':      1 if self._slipping else 0,
            'brownout':      1 if self._brownout else 0,
            'gravity':       self._get_gravity_force()
        })
        if self.controller is not None:
            point.update(self.controller.get_data_point())
        return point

    def _add_data_point(self):
        self.data_points.append(self._get_data_point())

    def get_data_points(self):
        return self.data_points

    def get_final(self, key):
        return self.data_points[-1][key]

    def calc(self):
        self.update()
        self._acceleration = self._calc_max_accel(self._velocity)  # compute accel at t=0
        self._add_data_point()  # output values at t=0

        # self._integrate_with_euler()
        self._integrate_with_heun()  # numerically integrate and output using Heun's method

    def get_type(self):
        return self.__class__.__name__[:-5]

    def get_info(self):
        return ("{0}x{1}".format(self.motors.__class__.__name__,
                                 self.num_motors) if self.name is None else self.name) + \
               " @ {0}:1 - {1}m".format(round(self.gear_ratio, 3), round(self.effective_diameter, 2))

    def to_str(self):
        return "." + self.get_info() + \
               (" <{}A".format(self.motor_current_limit) if self.motor_current_limit else "") + \
               (" <{}V".format(self.motor_voltage_limit) if self.motor_voltage_limit else "")

    def to_json(self):
        output = {
            'k_resistance_s':         self.k_resistance_s,
            'k_resistance_v':         self.k_resistance_v,
            'k_gearbox_efficiency':   self.k_gearbox_efficiency,
            'gear_ratio':             self.gear_ratio,
            'effective_diameter':     self.effective_diameter,
            'incline_angle':          self.incline_angle,
            'effective_mass':         self.effective_mass,
            'check_for_slip':         self.check_for_slip,
            'coeff_kinetic_friction': self.coeff_kinetic_friction,
            'coeff_static_friction':  self.coeff_static_friction,
            'motor_current_limit':    self.motor_current_limit,
            'motor_voltage_limit':    self.motor_voltage_limit,
            'battery_voltage':        self.battery_voltage,
            'resistance_com':         self.resistance_com,
            'resistance_one':         self.resistance_one,
            'time_step':              self.time_step,
            'simulation_time':        self.simulation_time,
            'max_dist':               self.max_dist
        }
        output.update([('motor_' + k, v) for k, v in self.motors.to_json().items()])
        return output
