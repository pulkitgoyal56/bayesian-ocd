from copy import deepcopy

import numpy as np
# import matplotlib.pyplot as plt

from cv2 import resize, INTER_LINEAR  # type: ignore
from gym import Env
from gym.spaces import box
from gym.utils import seeding
import pybullet

from car import THH
from plane import Plane


def dis(p1, p2):
    return ((p1[0] - p2[0]) ** 2  + (p1[1] - p2[1]) ** 2) ** 0.5


class TMazeEnv(Env):
    metadata = {'render.modes': ['human']}

    def __init__(self, mode='DIRECT', obs='vision', action_repeats=6, reward_scales=[1000, 1000],
                 target_setting="either", init_position_randomness=0.0, return_depth=False, seed=0, collision_punishment=1.0):

        np.random.seed(seed)
        np.random.default_rng(seed)

        if not obs == 'vision':
            self.observation_space = box.Box(
                low=np.array([-np.inf] * 6, dtype=np.float32),
                high=np.array([np.inf] * 6, dtype=np.float32))
        else:
            self.observation_space = box.Box(
                low=np.zeros([4 if return_depth else 3, 16, 64], dtype=np.float32),
                high=np.ones([4 if return_depth else 3, 16, 64], dtype=np.float32))

        self.action_space = box.Box(
            low=np.array([-1, -1.], dtype=np.float32),
            high=np.array([1, 1.], dtype=np.float32))

        self.np_random, _ = seeding.np_random(seed)
        self.info_shape = [2]

        self.obs = obs
        self.return_depth = return_depth

        assert target_setting in ['either', 'switching', 'random']
        self.target_setting = target_setting
        self.init_position_randomness = init_position_randomness

        self.reward_scales = reward_scales
        self.collision_punishment = collision_punishment

        if mode == 'GUI':
            self.client = pybullet.connect(pybullet.GUI)
        elif mode == 'DIRECT':
            self.client = pybullet.connect(pybullet.DIRECT)

        # Reduce length of episodes for RL algorithms
        pybullet.setTimeStep(1/30, self.client)

        self.action_repeats = action_repeats
        self.n_episode = 0

        self.zoom_coef = 2.0

        self.car: THH = None  # type: ignore
        self.goal = None
        self.done = False
        self.prev_dist_to_goal = None
        # self.rendered_img = None
        self.render_rot_matrix = None
        self.reset()
        pybullet.resetDebugVisualizerCamera(cameraDistance=8 * self.zoom_coef, cameraYaw=0, cameraPitch=-60,
                                     cameraTargetPosition=[0, -2.5 * self.zoom_coef, 2.5 * self.zoom_coef],
                                     physicsClientId=self.client)

    def step(self, action):
        # Feed action to the car and get observation of car's state

        collision = 0
        for _ in range(self.action_repeats):
            self.car.apply_action(action)
            pybullet.stepSimulation()

            for wallUId in self.wallUIds:
                self.contact_points = pybullet.getContactPoints(self.car.car, wallUId)
                if len(self.contact_points) > 0:
                    collision = 1

        if collision:
            for _ in range(int(self.action_repeats * 2)):
                # buffering
                self.car.apply_action(np.zeros_like(action))
                pybullet.stepSimulation()

        car_ob = self.car.get_position()

        reward = 0

        if not isinstance(self.goal_position[0], list):
            if abs(car_ob[0] - self.goal_position[0]) < 0.75 * self.zoom_coef and abs(car_ob[1] - self.goal_position[1]) < 0.75 * self.zoom_coef:
                reward += self.reward_scales
                self.done = True
        else:
            for i, goal_position in enumerate(self.goal_position):
                if abs(car_ob[0] - goal_position[0]) < 0.75 * self.zoom_coef and abs(car_ob[1] - goal_position[1]) < 0.75 * self.zoom_coef:
                    reward += self.reward_scales[i]
                    self.done = True
                    break
        
        if collision and reward < max(self.reward_scales):
            reward -= self.collision_punishment  # collision punishment
        
        self.prev_car_xy = deepcopy(car_ob[:2])

        ob = np.array(car_ob, dtype=np.float32)
        frame = self.render()
        vision = np.swapaxes(np.swapaxes(frame, 0, 2), 1, 2)

        self.info = {"ob": ob}

        if self.obs == 'vision':
            return vision, reward, self.done, False, self.info
        elif self.obs == 'both':
            return (ob, vision), reward, self.done, False, dict()
        else:
            return ob, reward, self.done, False, {"vision":vision}


    def createObjects(self, pybullet):
        # Comment: This function create objects including walls and Goals

        wallsColBoxIds = []
        wallsVisualShapeIds = []
        wallBasePositions = []
        wallBaseOrientations = []

        wallHeight = self.zoom_coef * 1

        zoom_coef = self.zoom_coef

        # top-left
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[0.495 * zoom_coef, 1.995 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[0.5 * zoom_coef, 2 * zoom_coef, wallHeight],
            rgbaColor=[0.8000, 0.38000, 0.1000, 1]))
        wallBasePositions.append([-4.5 * zoom_coef, 1 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])

        # top-right
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[0.495 * zoom_coef, 1.995 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[0.5 * zoom_coef, 2 * zoom_coef, wallHeight],
            rgbaColor=[0.1000, 0.3800, 0.8000, 1]))
        wallBasePositions.append([4.5 * zoom_coef, 1 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])

        # top
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[2.495 * zoom_coef, 0.495 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[2.5 * zoom_coef, 0.5 * zoom_coef, wallHeight],
            rgbaColor=[0.5200, 0.5200, 0.5200, 1]))
        wallBasePositions.append([0 * zoom_coef, 2.5 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])

        # bottom
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[1.495 * zoom_coef, 0.495 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[1.5 * zoom_coef, 0.5 * zoom_coef, wallHeight],
            rgbaColor=[0.7200, 0.2400, 0.7200, 1]))
        wallBasePositions.append([0 * zoom_coef, -4.5 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])


        # middle-left
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[1.124 * zoom_coef, 0.495 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[1.25 * zoom_coef, 0.5 * zoom_coef, wallHeight],
            rgbaColor=[0.8000, 0.5000, 0.5000, 1]))
        wallBasePositions.append([-2.75 * zoom_coef, -0.5 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])


        # middle-right
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[1.124 * zoom_coef, 0.495 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[1.25 * zoom_coef, 0.5 * zoom_coef, wallHeight],
            rgbaColor=[0.5000, 0.5000, 0.8000, 1]))
        wallBasePositions.append([2.75 * zoom_coef, -0.5 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])


        # bottom-left
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[0.495 * zoom_coef, 1.995 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[0.495 * zoom_coef, 1.995 * zoom_coef, wallHeight],
            rgbaColor=[0.5200, 0.5200, 0.5200, 1]))
        wallBasePositions.append([-1 * zoom_coef, -2 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])

        # bottom-right
        wallsColBoxIds.append(pybullet.createCollisionShape(
            pybullet.GEOM_BOX, halfExtents=[0.495 * zoom_coef, 1.995 * zoom_coef, wallHeight]))
        wallsVisualShapeIds.append(pybullet.createVisualShape(
            pybullet.GEOM_BOX, halfExtents=[0.495 * zoom_coef, 1.995 * zoom_coef, wallHeight],
            rgbaColor=[0.5200, 0.5200, 0.5200, 1]))
        wallBasePositions.append([1 * zoom_coef, -2 * zoom_coef, wallHeight])
        wallBaseOrientations.append([0, 0, 0, 1])

        mass = 99999999  # ~ fixed

        wallUIds = []
        for (colBoxId, visualShapeId, basePosition, baseOrientation) in zip(
                wallsColBoxIds, wallsVisualShapeIds, wallBasePositions, wallBaseOrientations):
            wallUIds.append(pybullet.createMultiBody(baseMass=mass,
                                                     baseCollisionShapeIndex=colBoxId,
                                                     baseVisualShapeIndex=visualShapeId,
                                                     basePosition=basePosition,
                                                     baseOrientation=baseOrientation))
        for wallUId in wallUIds:
            pybullet.changeDynamics(wallUId, -1, lateralFriction=0.)

        return wallUIds

    def generate_goal(self, goal_pos=None):

        goal_positions = []
        goal_positions.append([-3.25, 2.75])
        goal_positions.append([3.25, 2.75])

        for position in goal_positions:
            position[0] = position[0] * self.zoom_coef
            position[1] = position[1] * self.zoom_coef

        if goal_pos is None:
            tmp = self.np_random.integers(0, 2)
        else:
            tmp = goal_pos

        goal_position = goal_positions[tmp]

        return goal_position

    def reset(self, start_pos=None, start_orientation=None, goal_pos=None):  # type: ignore
        self.done = False

        pybullet.resetSimulation(self.client)
        pybullet.setGravity(0, 0, -9.8)
        # Reload the plane and car
        self.plane = Plane(self.client)

        pybullet.changeDynamics(self.plane.id, linkIndex=-1, lateralFriction=10.0)

        if goal_pos is not None:
            self.goal_position = self.generate_goal(goal_pos)
        elif self.target_setting == 'random':
            self.goal_position = self.generate_goal(None)
        elif self.target_setting == 'switching':
            self.goal_position = [-self.goal_position[0], self.goal_position[1]]
        elif self.target_setting == 'either':
            self.goal_position = [self.generate_goal(0), self.generate_goal(1)]

        if start_orientation is None:
            theta = np.pi / 2
        else:
            theta = start_orientation

        z0 = 0.5

        self.wallUIds = self.createObjects(pybullet=pybullet)

        # genetate initial position of the robot
        if start_pos is None:
            tmp1 = self.np_random.uniform(-1, 1)
            tmp2 = self.np_random.uniform(-1, 1)

            init_position = [0, -2.5]

            init_position[0] = (init_position[0] + tmp1 * self.init_position_randomness) * self.zoom_coef
            init_position[1] = (init_position[1] + tmp2 * self.init_position_randomness) * self.zoom_coef

            self.init_position = init_position + [z0]

        else:
            self.init_position = start_pos + [z0]

        self.car = THH(self.client, baseOrientation=pybullet.getQuaternionFromEuler([0, 0, theta]),
                        basePosition=self.init_position, speed=5.0)

        for _ in range(600):
            pybullet.stepSimulation()  # initialize

        # Get observation to return
        car_ob = self.car.get_position()

        self.prev_car_xy = car_ob[:2]

        self.n_episode += 1

        self.info = {"ob": np.array(car_ob, dtype=np.float32)}

        if self.obs == 'vision':
            frame = self.render()
            return np.swapaxes(np.swapaxes(frame, 0, 2), 1, 2), dict()
        elif self.obs == 'both':
            frame = self.render()
            proprioception = np.array(car_ob, dtype=np.float32)
            vision = np.swapaxes(np.swapaxes(frame, 0, 2), 1, 2)
            return (proprioception, vision), dict()
        else:
            return np.array(car_ob, dtype=np.float32), dict()

    def render(self, mode='rgbd_array'):
        # Base information
        car_id, client_id = self.car.get_ids()
        proj_matrix = pybullet.computeProjectionMatrixFOV(fov=90, aspect=1,
                                                   nearVal=0.025 * self.zoom_coef, farVal=20 * self.zoom_coef)
        pos, ori = [list(coor) for coor in
                    pybullet.getBasePositionAndOrientation(car_id, client_id)]

        pos[2] += 1.0

        # Rotate camera direction
        rot_mat = np.array(pybullet.getMatrixFromQuaternion(ori)).reshape(3, 3)
        camera_vec = np.matmul(rot_mat, [1, 0, 0])
        up_vec = np.matmul(rot_mat, np.array([0, 0, 1]))
        view_matrix = pybullet.computeViewMatrix(pos, pos + camera_vec, up_vec)

        # Display image
        _, _, frame, depth, _ = pybullet.getCameraImage(50, 50, view_matrix, proj_matrix)
        depth = np.array(depth).astype(np.float32)
        frame = np.reshape(frame, (50, 50, 4)).astype(np.float32) / 255.0
        frame = resize(frame, (16, 16), interpolation=INTER_LINEAR)

        # convert to true depth image
        true_depth = (20 * self.zoom_coef) * (0.025 * self.zoom_coef) / (
            (20 * self.zoom_coef) - ((20 * self.zoom_coef) - (0.025 * self.zoom_coef)) * depth)

        depth_sensory = np.exp(- true_depth/ self.zoom_coef / 3)
        depth_sensory = np.reshape(depth_sensory, (50, 50))
        depth_sensory = resize(depth_sensory, (16, 16), interpolation=INTER_LINEAR)

        tmp = pybullet.getEulerFromQuaternion(ori)
        tmp2 = list(tmp)
        tmp2[2] += 1 * np.pi / 2
        ori2 =  pybullet.getQuaternionFromEuler(tmp2)
        rot_mat = np.array(pybullet.getMatrixFromQuaternion(ori2)).reshape(3, 3)
        camera_vec = np.matmul(rot_mat, [1, 0, 0])
        up_vec = np.matmul(rot_mat, np.array([0, 0, 1]))
        view_matrix = pybullet.computeViewMatrix(pos, pos + camera_vec, up_vec)

        # Display image
        _, _, frame2, depth2, _ = pybullet.getCameraImage(50, 50, view_matrix, proj_matrix)
        depth2 = np.array(depth2).astype(np.float32)
        frame2 = np.reshape(frame2, (50, 50, 4)).astype(np.float32) / 255.0
        frame2 = resize(frame2, (16, 16), interpolation=INTER_LINEAR)

        true_depth = (20 * self.zoom_coef) * (0.025 * self.zoom_coef) / (
            (20 * self.zoom_coef) - ((20 * self.zoom_coef) - (0.025 * self.zoom_coef)) * depth2)

        depth_sensory2 = np.exp(- true_depth / self.zoom_coef / 3)
        depth_sensory2 = np.reshape(depth_sensory2, (50, 50))
        depth_sensory2 = resize(depth_sensory2, (16, 16), interpolation=INTER_LINEAR)

        tmp = pybullet.getEulerFromQuaternion(ori)
        tmp3 = list(tmp)
        tmp3[2] += 2 * np.pi / 2
        ori3 = pybullet.getQuaternionFromEuler(tmp3)
        rot_mat = np.array(pybullet.getMatrixFromQuaternion(ori3)).reshape(3, 3)
        camera_vec = np.matmul(rot_mat, [1, 0, 0])
        up_vec = np.matmul(rot_mat, np.array([0, 0, 1]))
        view_matrix = pybullet.computeViewMatrix(pos, pos + camera_vec, up_vec)

        # Display image
        _, _, frame3, depth3, _ = pybullet.getCameraImage(50, 50, view_matrix, proj_matrix)
        depth3 = np.array(depth3).astype(np.float32)
        frame3 = np.reshape(frame3, (50, 50, 4)).astype(np.float32) / 255.0
        frame3 = resize(frame3, (16, 16), interpolation=INTER_LINEAR)

        true_depth = (20 * self.zoom_coef) * (0.025 * self.zoom_coef) / (
            (20 * self.zoom_coef) - ((20 * self.zoom_coef) - (0.025 * self.zoom_coef)) * depth3)

        depth_sensory3 = np.exp(- true_depth / self.zoom_coef / 3)
        depth_sensory3 = np.reshape(depth_sensory3, (50, 50))
        depth_sensory3 = resize(depth_sensory3, (16, 16), interpolation=INTER_LINEAR)

        tmp = pybullet.getEulerFromQuaternion(ori)
        tmp4 = list(tmp)
        tmp4[2] += 3 * np.pi / 2
        ori4 = pybullet.getQuaternionFromEuler(tmp4)
        rot_mat = np.array(pybullet.getMatrixFromQuaternion(ori4)).reshape(3, 3)
        camera_vec = np.matmul(rot_mat, [1, 0, 0])
        up_vec = np.matmul(rot_mat, np.array([0, 0, 1]))
        view_matrix = pybullet.computeViewMatrix(pos, pos + camera_vec, up_vec)

        # Display image
        _, _, frame4, depth4, _ = pybullet.getCameraImage(50, 50, view_matrix, proj_matrix)
        depth4 = np.array(depth4).astype(np.float32)
        frame4 = np.reshape(frame4, (50, 50, 4)).astype(np.float32) / 255.0
        frame4 = resize(frame4, (16, 16), interpolation=INTER_LINEAR)

        true_depth = (20 * self.zoom_coef) * (0.025 * self.zoom_coef) / (
            (20 * self.zoom_coef) - ((20 * self.zoom_coef) - (0.025 * self.zoom_coef)) * depth4)

        depth_sensory4 = np.exp(- true_depth / self.zoom_coef / 3)
        depth_sensory4 = np.reshape(depth_sensory4, (50, 50))
        depth_sensory4 = resize(depth_sensory4, (16, 16), interpolation=INTER_LINEAR)

        if self.return_depth:
            return np.concatenate((np.concatenate((frame3[:, 8:, :3], frame2[:, :, :3], frame[:, :, :3],
                                                    frame4[:, :, :3], frame3[:, :8, :3]), axis=1),
                np.concatenate((depth_sensory3[:, 8:, None], depth_sensory2[:, :, None], depth_sensory[:, :, None],
                                depth_sensory4[:, :, None], depth_sensory3[:, :8, None]), axis=1)), axis=-1)
        else:
            return np.concatenate((frame3[:, 8:, :3], frame2[:, :, :3], frame[:, :, :3],
                                    frame4[:, :, :3], frame3[:, :8, :3]), axis=1)

    @staticmethod
    def draw_tmaze(plot_exit_line=False):
        import matplotlib.pyplot as plt

        zoom_coef = 2

        xv = []
        yv = []
        cv = []

        # top-left
        xv.append([-5, -4, -4, -5, -5])
        yv.append([-1, -1, 3, 3, -1])
        cv.append([0.8000, 0.38000, 0.1000])

        # top-right
        xv.append([5, 4, 4, 5, 5])
        yv.append([-1, -1, 3, 3, -1])
        cv.append([0.1000, 0.3800, 0.8000])

        # top
        xv.append([2.5, -2.5, -2.5, 2.5, 2.5])
        yv.append([2, 2, 3, 3, 2])
        cv.append([0.5200, 0.5200, 0.5200])

        # middle-left
        xv.append([-1.5, -4, -4, -1.5, -1.5])
        yv.append([-1, -1, 0, 0, -1])
        cv.append([0.8000, 0.5000, 0.5000])

        # middle-right
        xv.append([1.5, 4, 4, 1.5, 1.5])
        yv.append([-1, -1, 0, 0, -1])
        cv.append([0.5000, 0.5000, 0.8000])

        # bottom-left
        xv.append([-1.5, -1.5, -0.5, -0.5, -0.5])
        yv.append([-4, 0, 0, -4, -4])
        cv.append([0.5200, 0.5200, 0.5200])

        # bottom-right
        xv.append([1.5, 1.5, 0.5, 0.5, 0.5])
        yv.append([-4, 0, 0, -4, -4])
        cv.append([0.5200, 0.5200, 0.5200])

        # bottom
        xv.append([-1.5, -1.5, 1.5, 1.5, 1.5])
        yv.append([-4, -5, -5, -4, -4])
        cv.append([0.7200, 0.2400, 0.7200])

        if plot_exit_line:
            # exit line
            xv.append([-4, -2.5, -2.5, -4, -4])
            yv.append([2, 2, 2.05, 2.05, 2])
            cv.append([0.2200, 0.8200, 0.2200])

            # exit line
            xv.append([4, 2.5, 2.5, 4, 4])
            yv.append([2, 2, 2.05, 2.05, 2])
            cv.append([0.2200, 0.8200, 0.2200])

        for i in range(len(xv)):
            plt.fill([xi * zoom_coef for xi in xv[i]], 
                    [yi * zoom_coef for yi in yv[i]], 
                    color=cv[i], 
                    edgecolor='none')

        plt.xlim([-10.5, 10.5])
        plt.ylim([-10.5, 6.5])
        plt.axis('off')
        plt.box(False)
 
    def close(self):
        pybullet.disconnect(self.client)
