class CongestionControllerFactory(object):
    def __init__(self):
        pass

    @classmethod
    def get_congestion_controller(cls, controller_name):
        if controller_name == 'RL_noFrame':
            from rl.Congestion_controller.rlNoFrameCongestionController import RlCongestionController
            return RlCongestionController()
        if controller_name == 'RL':
            from rl.Congestion_controller.rlCongestionController import RlCongestionController
            return RlCongestionController()
