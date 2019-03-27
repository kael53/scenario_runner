#!/usr/bin/env python

#
# This work is licensed under the terms of the MIT license.
# For a copy, see <https://opensource.org/licenses/MIT>.

"""
Control Loss Vehicle scenario:

The scenario realizes that the vehicle looses control due to
bad road conditions, etc. and checks to see if the vehicle
regains control and corrects it's course.
"""

import random

import py_trees

from srunner.scenariomanager.atomic_scenario_behavior import *
from srunner.scenariomanager.atomic_scenario_criteria import *
from srunner.scenariomanager.timer import TimeOut
from srunner.scenarios.basic_scenario import *
from srunner.scenarios.scenario_helper import *

CONTROL_LOSS_SCENARIOS = [
    "ControlLoss"
]


class ControlLoss(BasicScenario):

    """
    Implementation of "Control Loss Vehicle" (Traffic Scenario 01)
    """

    category = "ControlLoss"

    timeout = 60            # Timeout of scenario in seconds

    def __init__(self, world, ego_vehicle, config, randomize=False, debug_mode=False, criteria_enable=True):
        """
        Setup all relevant parameters and create scenario
        """
        # ego vehicle parameters
        self._no_of_jitter = 10
        self._noise_mean = 0      # Mean value of steering noise
        self._noise_std = 0.06   # Std. deviation of steering noise
        self._dynamic_mean_for_steer = 0.01
        self._dynamic_mean_for_throttle = 0.75
        self._abort_distance_to_intersection = 10
        self._start_distance = 20
        self._trigger_dist = 2
        self._end_distance = 100
        self._ego_vehicle_max_steer = 0.0
        self._ego_vehicle_max_throttle = 1.0
        self._ego_vehicle_target_velocity = 15
        self._map = CarlaDataProvider.get_map()
        self.loc_list = []
        self.obj = []
        super(ControlLoss, self).__init__("ControlLoss",
                                          ego_vehicle,
                                          config,
                                          world,
                                          debug_mode,
                                          criteria_enable=criteria_enable)

    def _initialize_actors(self, config):
        """
        Custom initialization
        """
        first_loc, _ = get_location_in_distance(self.ego_vehicle, 18)
        second_loc, _ = get_location_in_distance(self.ego_vehicle, 47)
        third_loc, _ = get_location_in_distance(self.ego_vehicle, 81)
        self.loc_list.extend([first_loc, second_loc, third_loc])
        for loc in self.loc_list:
            if self._map.name == 'Town02':
                loc.z += 0.2

        first_transform = carla.Transform(self.loc_list[0])
        sec_transform = carla.Transform(self.loc_list[1])
        third_transform = carla.Transform(self.loc_list[2])

        first_debris = CarlaActorPool.request_new_actor('static.prop.dirtdebris01', first_transform)
        second_debris = CarlaActorPool.request_new_actor('static.prop.dirtdebris01', sec_transform)
        third_debris = CarlaActorPool.request_new_actor('static.prop.dirtdebris01', third_transform)

        self.obj.extend([first_debris, second_debris, third_debris])
        for debris in self.obj:
            debris.set_simulate_physics(False)

        self.other_actors.append(first_debris)
        self.other_actors.append(second_debris)
        self.other_actors.append(third_debris)

    def _create_behavior(self):
        """
        The scenario defined after is a "control loss vehicle" scenario. After
        invoking this scenario, it will wait until the vehicle drove a few meters
        (_start_distance), and then perform a jitter action. Finally, the vehicle
        has to reach a target point (_end_distance). If this does not happen within
        60 seconds, a timeout stops the scenario
        """

        # start condition
        location, _ = get_location_in_distance(self.ego_vehicle, self._start_distance)
        start_condition = InTriggerDistanceToLocation(self.ego_vehicle, location, 10.0)
        for i in range(self._no_of_jitter):
            noise = random.gauss(self._noise_mean, self._noise_std)
            noise = abs(noise)
            self._ego_vehicle_max_steer = min(0, -(noise - self._dynamic_mean_for_steer))
            self._ego_vehicle_max_throttle = min(noise + self._dynamic_mean_for_throttle, 1)
            # turn vehicle
            turn = AddNoiseToVehicle(self.ego_vehicle, self._ego_vehicle_max_steer,
                                     self._ego_vehicle_max_throttle, name="jittering"+str(i))
        jitter_action = py_trees.composites.Parallel("Jitter",
                                                     policy=py_trees.common.ParallelPolicy.SUCCESS_ON_ONE)
        # Abort jitter_sequence, if the vehicle is approaching an intersection
        jitter_abort = InTriggerDistanceToNextIntersection(self.ego_vehicle, self._abort_distance_to_intersection)
        # endcondition: Check if vehicle reached waypoint _end_distance from here:
        end_condition = DriveDistance(self.ego_vehicle, self._end_distance)

        # Build behavior tree
        sequence = py_trees.composites.Sequence("Sequence Behavior")
        jitter = py_trees.composites.Sequence("Jitter Behavior")
        jitter.add_child(turn)
        jitter.add_child(InTriggerDistanceToLocation(self.ego_vehicle, self.loc_list[1], self._trigger_dist))
        jitter.add_child(turn)
        jitter.add_child(InTriggerDistanceToLocation(self.ego_vehicle, self.loc_list[2], self._trigger_dist))
        jitter.add_child(turn)
        jitter_action.add_child(jitter)
        jitter_action.add_child(jitter_abort)
        sequence.add_child(start_condition)
        sequence.add_child(jitter_action)
        sequence.add_child(end_condition)
        return sequence

    def _create_test_criteria(self):
        """
        A list of all test criteria will be created that is later used
        in parallel behavior tree.
        """
        criteria = []

        collision_criterion = CollisionTest(self.ego_vehicle)
        criteria.append(collision_criterion)

        return criteria

    def __del__(self):
        """
        Remove all actors upon deletion
        """
        self.remove_all_actors()