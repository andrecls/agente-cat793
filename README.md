cd ~/cco_ia
source ~/simulador_ws/install/setup.bash
ros2 bag play rosbag2_wellerson_05112025 -l

cd ~/cco_ia
source ~/simulador_ws/install/setup.bash
python3 Painel.py
