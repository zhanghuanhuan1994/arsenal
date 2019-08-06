class CongestionControllerFactory(object):
    def __init__(self):
        pass

    @classmethod
    def get_congestion_controller(cls, controller_name):

        if controller_name == 'gcc':
            from il.Congestion_controller.gccCongestionController import GccCongestionController
            return GccCongestionController()

        # IL without
        if controller_name == 'IL':
            from il.Congestion_controller.daggerCongestionController import DaggerCongestionController
            return DaggerCongestionController()

        if controller_name == 'RL':
            from il.Congestion_controller.rlCongestionController import RlCongestionController
            return RlCongestionController()

        # IL with frame
        if controller_name == "IL_with_frame":
            from il.Congestion_controller.daggerCongestionController_with_frame import DaggerCongestionController
            return DaggerCongestionController()
