import os

import pybullet


class Plane:
    def __init__(self, client):
        f_name = os.path.join(os.path.dirname(__file__), 'simpleplane.urdf')
        self.id = pybullet.loadURDF(fileName=f_name,
                             basePosition=[0, 0, -0.01],
                             physicsClientId=client)




