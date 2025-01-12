import numpy as np

import rospy
import ros_numpy

from geometry_msgs.msg import Twist, TwistStamped, Vector3Stamped
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Illuminance, Image, Imu, Joy, LaserScan, NavSatFix, NavSatStatus
from std_msgs.msg import Bool, Float32, Float64MultiArray

from badgr.jackal.utils.gps import latlong_to_utm


def numpify_image_msg(msg):
    msg.__class__ = Image
    return ros_numpy.numpify(msg)


class JackalSubscriber(object):
    
    odom_topic_name = rospy.get_param("odom_topic_name", "/odom")
    lidar_topic_name = rospy.get_param("lidar_topic_name","/scan")
    cam_topic_name = rospy.get_param("cam_topic_name","/rgb")
    cmd_topic_name = rospy.get_param("cmd_topic_name","/cmd")
    mag_topic_name = rospy.get_param("mag_topic_name","/mag")
    imu_topic_name = "/imu"

    topics_to_msgs = dict((
        ('/collision/any', Bool),
        ('/collision/physical', Bool),
        ('/collision/close', Bool),
        ('/collision/flipped', Bool),
        ('/collision/stuck', Bool),
        ('/collision/outside_geofence', Bool),

        (lidar_topic_name, LaserScan), #('/rplidar/scan', LaserScan),

        ('/imu_um7/compass_bearing', Float32),
        ('/imu_um7/mag', Vector3Stamped),
        ('/imu_um7/data', Imu),

        ('/navsat/fix', NavSatFix),
        ('/navsat/vel', TwistStamped),

        (odom_topic_name, Odometry), #('/odometry/filtered', Odometry),
        (imu_topic_name, Imu),      # ('/imu/data_raw', Imu),

        ('/cmd_vel', Twist),

        (cam_topic_name, Image),  # ('/cam_left/image_raw', Image),
        ('/cam_right/image_raw', Image),
        ('/teraranger_evo_thermal/raw_temp_array', Float64MultiArray),

        ('/android/illuminance', Illuminance),

        ('/bluetooth_teleop/joy', Joy)
    ))

    names_topics_funcs = (
        ('collision/any', '/collision/any', lambda msg: msg.data),
        ('collision/physical', '/collision/physical', lambda msg: msg.data),
        ('collision/close', '/collision/close', lambda msg: msg.data),
        ('collision/flipped', '/collision/flipped', lambda msg: msg.data),
        ('collision/stuck', '/collision/stuck', lambda msg: msg.data),
        ('collision/outside_geofence', '/collision/outside_geofence', lambda msg: msg.data),

        ('lidar', lidar_topic_name, lambda msg: msg.ranges),

        ('imu/compass_bearing', '/imu_um7/compass_bearing', lambda msg: msg.data),
        ('imu/magnetometer', '/imu_um7/mag', lambda msg: np.array([msg.vector.x,
                                                     msg.vector.y,
                                                     msg.vector.z])),
        ('imu/linear_acceleration', '/imu_um7/data', lambda msg: np.array([msg.linear_acceleration.x,
                                                            msg.linear_acceleration.y,
                                                            msg.linear_acceleration.z])),
        ('imu/angular_velocity', '/imu_um7/data', lambda msg: np.array([msg.angular_velocity.x,
                                                         msg.angular_velocity.y,
                                                         msg.angular_velocity.z])),
        ('gps/is_fixed', '/navsat/fix', lambda msg: msg.status.status >= NavSatStatus.STATUS_FIX),
        ('gps/latlong', '/navsat/fix', lambda msg: np.array([msg.latitude, msg.longitude])),
        ('gps/utm', '/navsat/fix', lambda msg: latlong_to_utm(np.array([msg.latitude, msg.longitude]))),
        ('gps/altitude', '/navsat/fix', lambda msg: msg.altitude),
        ('gps/velocity', '/navsat/vel', lambda msg: np.array([msg.twist.linear.x,
                                                              msg.twist.linear.y,
                                                              msg.twist.linear.z])),

        ('jackal/position', odom_topic_name, lambda msg: np.array([msg.pose.pose.position.x,
                                                    msg.pose.pose.position.y,
                                                    msg.pose.pose.position.z])),
        ('jackal/yaw', odom_topic_name, lambda msg: np.arctan2(2*msg.pose.pose.orientation.w *
                                                msg.pose.pose.orientation.z,
                                                1 - 2 * msg.pose.pose.orientation.z *
                                                msg.pose.pose.orientation.z)),
        ('jackal/linear_velocity', odom_topic_name, lambda msg: msg.twist.twist.linear.x),
        ('jackal/angular_velocity', odom_topic_name, lambda msg: msg.twist.twist.angular.z),
        ('jackal/imu/linear_acceleration', imu_topic_name, lambda msg: np.array([msg.linear_acceleration.x,
                                                                   msg.linear_acceleration.y,
                                                                   msg.linear_acceleration.z])),
        ('jackal/imu/angular_velocity', imu_topic_name, lambda msg: np.array([msg.angular_velocity.x,
                                                                msg.angular_velocity.y,
                                                                msg.angular_velocity.z])),

        ('commands/linear_velocity', cmd_topic_name, lambda msg: msg.linear.x),
        ('commands/angular_velocity', cmd_topic_name, lambda msg: msg.angular.z),

        ('images/rgb_left', cam_topic_name, lambda msg: numpify_image_msg(msg)),
        ('images/rgb_right', '/cam_left/image_raw', lambda msg: numpify_image_msg(msg)),
        ('images/thermal', '/teraranger_evo_thermal/raw_temp_array',
         lambda msg: np.fliplr(np.array(msg.data).reshape(32, 32))),

        ('android/illuminance', '/android/illuminance', lambda msg: msg.illuminance),

        ('joy', '/bluetooth_teleop/joy', lambda msg: msg)
    )

    names_to_topics = {name: topic for name, topic, _ in names_topics_funcs}
    names_to_funcs = {name: func for name, _, func in names_topics_funcs}

    def __init__(self, names=None):
        self._names = names or tuple(JackalSubscriber.names_to_topics.keys())
        self._d_msg = dict()

        self._topics = set([JackalSubscriber.names_to_topics[name] for name in self._names])
        for topic in self._topics:
            print(f"Topic to subscribe: {topic}")
            rospy.Subscriber(topic, JackalSubscriber.topics_to_msgs[topic],
                             callback=self.update_msg, callback_args=(topic,), queue_size=1)

    @property
    def is_all_topics_received(self):
        tmp = len(self._topics.difference(set(self._d_msg.keys())))
        # print(self._topics)
        # print(self._d_msg.keys())
        # print(tmp)
        return  tmp == 0

    def update_msg(self, msg, args):
        topic = args[0]
        # rospy.loginfo(f"Msg from {topic}")
        self._d_msg[topic] = msg

    def get(self, names=None):
        while not rospy.is_shutdown() and not self.is_all_topics_received:
            print('Waiting for all topics to be received...')
            rospy.sleep(0.2)

        names = names or self._names

        d = {}
        for name in names:
            func = JackalSubscriber.names_to_funcs[name]
            msg = self._d_msg[JackalSubscriber.names_to_topics[name]]
            value = func(msg)
            if isinstance(value, np.ndarray) and np.issubdtype(value.dtype, np.float):
                value = value.astype(np.float32)
            d[name] = value
        return d
