from model import DrivetrainModel, plot_models, dump_model_csv
from model.motors import *
from model.motors import _775pro

if __name__ == "__main__":

    model = DrivetrainModel(CIM(6), gear_ratio=13, robot_mass=68, wheel_diameter=6 * 0.0254)

    model2 = DrivetrainModel(MiniCIM(6), gear_ratio=14, robot_mass=68, wheel_diameter=6 * 0.0254)

    model3 = DrivetrainModel(_775pro(8), gear_ratio=36, robot_mass=68, wheel_diameter=6 * 0.0254,
                             motor_voltage_limit=10, motor_current_limit=35)

    model.calc()
    model2.calc()
    model3.calc()

    plot_models(model, model2, model3, elements_to_plot=('pos', 'vel', 'current'))