"""
文件名: main_with_comparison.py
功能: 实时对比用户动作与标准动作，显示反馈
"""

import cv2
import numpy as np
import json
import os
from pose_detection import PoseDetector
from one_euro_filter import MultiPointFilter
from pose_comparator import PoseComparator

class YogaTutorSystem:
    """瑜伽教练系统"""
    
    def __init__(self, standard_pose_path):
        # 初始化各模块
        self.pose_detector = PoseDetector()
        self.mp_filter = MultiPointFilter(num_points=33)
        self.comparator = PoseComparator(standard_pose_path)
        
        # UI配置
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.colors = {
            'good': (0, 255, 0),      # 绿色
            'warning': (0, 165, 255),  # 橙色
            'error': (0, 0, 255),      # 红色
            'info': (255, 255, 255)    # 白色
        }
        
        # 统计
        self.score_history = []
        self.best_score = 0
    
    def run(self):
        """运行系统"""
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            print("❌ 无法打开摄像头")
            return
        
        # 设置摄像头分辨率
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        print(f"✅ 系统已启动 - 目标姿势: {self.comparator.pose_name}")
        print("按 'q' 退出, 'r' 重置最佳分数, 's' 截图")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 镜像翻转
            frame = cv2.flip(frame, 1)
            
            # 姿态检测
            results = self.pose_detector.pose.process(
                cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            )
            
            if results.pose_landmarks:
                # 提取并滤波关键点
                landmarks = self._extract_landmarks(results, frame.shape)
                filtered_landmarks = self.mp_filter.filter_landmarks(landmarks)
                
                # 计算用户角度
                user_angles = self._calculate_all_angles(filtered_landmarks)
                
                # 对比分析
                comparison_result = self.comparator.compare(user_angles)
                
                # 绘制骨骼
                self.pose_detector.mp_draw.draw_landmarks(
                    frame,
                    results.pose_landmarks,
                    self.pose_detector.mp_pose.POSE_CONNECTIONS
                )
                
                # 绘制UI
                frame = self._draw_ui(frame, comparison_result, user_angles)
                
                # 更新统计
                self._update_stats(comparison_result['score'])
            
            else:
                # 未检测到人体
                self._draw_no_pose_warning(frame)
            
            cv2.imshow('Yoga Tutor - 智能瑜伽教练', frame)
            
            # 键盘控制
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('r'):
                self.best_score = 0
                self.score_history = []
                print("📊 统计已重置")
            elif key == ord('s'):
                self._save_screenshot(frame)
        
        cap.release()
        cv2.destroyAllWindows()
    
    def _extract_landmarks(self, results, frame_shape):
        """提取关键点"""
        h, w = frame_shape[:2]
        landmarks = []
        for lm in results.pose_landmarks.landmark:
            landmarks.append({
                'x': lm.x * w,
                'y': lm.y * h,
                'z': lm.z,
                'visibility': lm.visibility
            })
        return landmarks
    
    def _calculate_all_angles(self, landmarks):
        """计算所有关节角度"""
        angles = {}
        
        angle_defs = {
            'left_elbow': ('left_shoulder', 'left_elbow', 'left_wrist'),
            'right_elbow': ('right_shoulder', 'right_elbow', 'right_wrist'),
            'left_knee': ('left_hip', 'left_knee', 'left_ankle'),
            'right_knee': ('right_hip', 'right_knee', 'right_ankle'),
            'left_shoulder': ('left_elbow', 'left_shoulder', 'left_hip'),
            'right_shoulder': ('right_elbow', 'right_shoulder', 'right_hip'),
            'left_hip': ('left_shoulder', 'left_hip', 'left_knee'),
            'right_hip': ('right_shoulder', 'right_hip', 'right_knee'),
        }
        
        for joint_name, (p1, p2, p3) in angle_defs.items():
            angle = self.pose_detector.calculate_angle(landmarks, p1, p2, p3)
            if angle is not None:
                angles[joint_name] = angle
        
        return angles
    
    def _draw_ui(self, frame, comparison_result, user_angles):
        """绘制用户界面"""
        h, w = frame.shape[:2]
        
        # 半透明信息面板
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (500, 300), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # 标题
        cv2.putText(frame, f"Pose: {comparison_result['pose_name']}", 
                   (20, 40), self.font, 0.8, self.colors['info'], 2)
        
        # 分数
        score = comparison_result['score']
        score_color = self._get_score_color(score)
        cv2.putText(frame, f"Score: {score:.1f}/100", 
                   (20, 80), self.font, 1.2, score_color, 3)
        
        # 最佳分数
        cv2.putText(frame, f"Best: {self.best_score:.1f}", 
                   (20, 115), self.font, 0.6, self.colors['good'], 2)
        
        # 反馈提示
        y_offset = 160
        feedback_items = comparison_result['feedback'][:3]  # 只显示前3条
        
        if not feedback_items:
            cv2.putText(frame, "Perfect! All joints correct!", 
                       (20, y_offset), self.font, 0.7, self.colors['good'], 2)
        else:
            for item in feedback_items:
                color = self.colors['error'] if item['severity'] == '严重' else self.colors['warning']
                cv2.putText(frame, item['message'], 
                           (20, y_offset), self.font, 0.6, color, 2)
                y_offset += 35
        
        # 右侧角度详情
        self._draw_angle_details(frame, comparison_result['deviations'], w)
        
        return frame
    
    def _draw_angle_details(self, frame, deviations, frame_width):
        """绘制角度详情"""
        x_start = frame_width - 350
        y_start = 30
        
        # 标题
        cv2.putText(frame, "Joint Angles", 
                   (x_start, y_start), self.font, 0.7, self.colors['info'], 2)
        
        y_offset = y_start + 40
        
        for joint, data in list(deviations.items())[:6]:  # 显示前6个关节
            # 关节名
            joint_cn = self.comparator._joint_name_cn(joint)
            
            # 颜色
            color = self.colors['good'] if data['is_correct'] else self.colors['error']
            
            # 显示
            text = f"{joint_cn}: {data['current']:.0f}deg ({data['standard']:.0f})"
            cv2.putText(frame, text, (x_start, y_offset), 
                       self.font, 0.5, color, 1)
            
            # 偏差指示器
            if not data['is_correct']:
                diff_text = f"({data['difference']:+.0f})"
                cv2.putText(frame, diff_text, (x_start + 250, y_offset),
                           self.font, 0.5, self.colors['warning'], 1)
            
            y_offset += 30
    
    def _draw_no_pose_warning(self, frame):
        """绘制未检测到姿势的警告"""
        h, w = frame.shape[:2]
        text = "No pose detected - Please stand in frame"
        text_size = cv2.getTextSize(text, self.font, 1, 2)[0]
        x = (w - text_size[0]) // 2
        y = (h + text_size[1]) // 2
        
        cv2.putText(frame, text, (x, y), self.font, 1, 
                   self.colors['warning'], 2)
    
    def _get_score_color(self, score):
        """根据分数返回颜色"""
        if score >= 90:
            return self.colors['good']
        elif score >= 70:
            return self.colors['warning']
        else:
            return self.colors['error']
    
    def _update_stats(self, score):
        """更新统计信息"""
        self.score_history.append(score)
        if score > self.best_score:
            self.best_score = score
    
    def _save_screenshot(self, frame):
        """保存截图"""
        import time
        filename = f"screenshot_{int(time.time())}.jpg"
        cv2.imwrite(filename, frame)
        print(f"📸 截图已保存: {filename}")

def main():
    """主函数"""
    print("=" * 60)
    print("瑜伽智能教练系统")
    print("=" * 60)
    
    # 列出可用的标准姿势
    pose_dir = "standard_poses"
    if not os.path.exists(pose_dir):
        print(f"❌ 标准姿势目录不存在: {pose_dir}")
        print("请先使用 standard_pose_extractor.py 提取标准动作")
        return
    
    pose_files = [f for f in os.listdir(pose_dir) if f.endswith('.json')]
    
    if not pose_files:
        print("❌ 未找到标准姿势文件")
        print("请先使用 standard_pose_extractor.py 提取标准动作")
        return
    
    print("\n可用的标准姿势:")
    for i, pose_file in enumerate(pose_files, 1):
        pose_name = pose_file.replace('.json', '')
        print(f"  {i}. {pose_name}")
    
    # 选择姿势
    choice = input("\n请选择姿势编号 (直接回车选择第一个): ").strip()
    
    if choice == '':
        choice = '1'
    
    try:
        idx = int(choice) - 1
        selected_pose = os.path.join(pose_dir, pose_files[idx])
    except:
        print("❌ 无效选择，使用第一个姿势")
        selected_pose = os.path.join(pose_dir, pose_files[0])
    
    # 启动系统
    system = YogaTutorSystem(selected_pose)
    system.run()

if __name__ == "__main__":
    main()