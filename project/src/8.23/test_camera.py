"""
文件名: test_camera.py
功能: 测试摄像头是否正常工作
这是你的第一个测试程序！
"""

import cv2

def main():
    # 打开摄像头（0表示默认摄像头）
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("❌ 无法打开摄像头！请检查：")
        print("   1. 摄像头是否被其他程序占用")
        print("   2. 摄像头驱动是否正常")
        return
    
    print("✅ 摄像头已打开！按 'q' 退出")
    
    while True:
        # 读取一帧
        ret, frame = cap.read()
        
        if not ret:
            print("❌ 无法读取画面")
            break
        
        # 在画面上显示文字
        cv2.putText(frame, "YogaTutor - Camera Test", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 显示画面
        cv2.imshow('Camera Test', frame)
        
        # 按 'q' 退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # 释放资源
    cap.release()
    cv2.destroyAllWindows()
    print("✅ 测试完成！")

if __name__ == "__main__":
    main()