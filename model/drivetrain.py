from model.generic import GenericModel
from model.motors import Motor


class DrivetrainModel(GenericModel):
    def __init__(self,
                 motors: Motor,
                 gear_ratio: float,
                 wheel_diameter: float,
                 robot_mass: float,
                 incline_angle=0,
                 motor_current_limit=None,
                 motor_voltage_limit=None,
                 k_gearbox_efficiency=0.7,
                 coeff_kinetic_friction=0.8,
                 coeff_static_friction=1.0,
                 k_resistance_s=0,
                 k_resistance_v=0,
                 battery_voltage=12.5,
                 resistance_com=0.013,
                 resistance_one=0.002,
                 max_dist=8,
                 time_step=0.001,
                 simulation_time=120.0):

        super().__init__(motors=motors,
                         k_resistance_s=k_resistance_s,
                         k_resistance_v=k_resistance_v,
                         k_gearbox_efficiency=k_gearbox_efficiency,
                         gear_ratio=gear_ratio,
                         effective_diameter=wheel_diameter,
                         effective_mass=robot_mass,
                         check_for_slip=True,
                         coeff_kinetic_friction=coeff_kinetic_friction,
                         coeff_static_friction=coeff_static_friction,
                         battery_voltage=battery_voltage,
                         resistance_com=resistance_com,
                         resistance_one=resistance_one,
                         time_step=time_step,
                         simulation_time=simulation_time,
                         max_dist=max_dist,
                         incline_angle=incline_angle,
                         motor_current_limit=motor_current_limit,
                         motor_voltage_limit=motor_voltage_limit)
