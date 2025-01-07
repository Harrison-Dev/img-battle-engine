# pip install opencv-python  
# pip install opencv-contrib-python
# pip install Pillow

import cv2
import os

# 文件名
name = "Hibike! Euphonium S2 01 [BD 1920x1080 HEVC-10bit OPUS ASSx2].mkv"

# 文件完整路径
video_file = f"./{name}"

# 截图输出路径
output_folder = f"./output_{name}_shoots/"


def compare_images(image1, image2):
    similarity_score = cv2.matchTemplate(image1, image2, cv2.TM_CCOEFF_NORMED)[0][0]
    return similarity_score



last_saved_image = None
threshold = 0.4

# 创建输出文件夹
if not os.path.exists(output_folder):
    os.makedirs(output_folder)

# 打开视频文件并获取视频信息
video_capture = cv2.VideoCapture(video_file)
num_frames = int(video_capture.get(cv2.CAP_PROP_FRAME_COUNT))

# 逐帧处理视频
for i in range(num_frames):
    # 读取当前帧
    ret, frame = video_capture.read()
    if not ret:
        break

    # 将当前帧缩放为100x100
    current_frame_resized = cv2.resize(frame, (100, 100))

    # 如果已经有最后保存的图像，则比较当前帧和最后保存的图像
    if last_saved_image is not None:
        # 计算相似度分数
        similarity_score = compare_images(current_frame_resized, last_saved_image)

        print(f"Frame {i} similarity: {similarity_score}")

        # 如果两个图像不同，则将当前帧保存到输出文件夹中
        if similarity_score < threshold:
            output_file = os.path.join(output_folder, f"{name}_frame_{i}.jpg")
            cv2.imwrite(output_file, frame)

    # 将当前帧设为最后保存的图像
    last_saved_image = current_frame_resized

# 释放资源
video_capture.release()