import sys
sys.path.remove('/opt/ros/kinetic/lib/python2.7/dist-packages')
import cv2
sys.path.append('/opt/ros/kinetic/lib/python2.7/dist-packages')

import argparse
from loguru import logger
import numpy as np
import os
import rospy
from geometry_msgs.msg import Twist

from badgr.file_manager import FileManager
from badgr.utils.python_utils import exit_on_ctrl_c, import_config
from badgr.utils import tf_utils

os.environ['TF_FORCE_GPU_ALLOW_GROWTH'] = 'true'

parser = argparse.ArgumentParser()
parser.add_argument('config', type=str)
parser.add_argument('--ckpt', type=int, default=None)
parser.add_argument('--gpu', type=int, default=0)
parser.add_argument('--gpu_frac', type=float, default=0.3)
parser.add_argument('--num_dones', type=float, default=np.inf)
args = parser.parse_args()

config_fname = os.path.abspath(args.config)
assert os.path.exists(config_fname), '{0} does not exist'.format(config_fname)
params = import_config(config_fname)

tf_utils.enable_static_execution(gpu=args.gpu, gpu_frac=args.gpu_frac)

file_manager = FileManager(params.exp_name, is_continue=True)
model = params.model.cls(params.model.kwargs_eval)

print(params.model.kwargs_eval)
planner = params.planner.cls(file_manager=file_manager, params=params.planner.kwargs)
env = params.env.cls(env_spec=params.env.env_spec, params=params.env.params)

### warm start the planner
obs, goal = env.reset()
planner.warm_start(model, obs, goal)

### restore policy
model.restore(ckpts_dir=file_manager.ckpts_dir, ckptnum=args.ckpt)

### eval loop

exit_on_ctrl_c()

# setup /cmd_vel publisher
cmd_pub = rospy.Publisher('/cmd_vel',Twist,queue_size=1)

done = True
num_dones = -1
while num_dones < args.num_dones:
    if done:
        obs, goal = env.reset()
        num_dones += 1
        logger.info('num_dones: {0}'.format(num_dones))

    get_action = planner.get_action(model, obs, goal)
    obs, goal, done = env.step(get_action)
    print(get_action.all_costs)
    # publish command
    msg = Twist()
    msg.linear.x = get_action.action.commands.linear_velocity
    msg.angular.z = -get_action.action.commands.angular_velocity
    cmd_pub.publish(msg)
    logger.info(f'command: v={msg.linear.x}, w={msg.angular.z}')

logger.info('Eval is done')
rospy.signal_shutdown(0)
