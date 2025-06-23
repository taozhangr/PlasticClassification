import sys
import os
import csv
from datetime import datetime
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QComboBox, QPushButton, QTextEdit, QLabel, QGridLayout, QStatusBar, QLineEdit,
    QFileDialog
)
from PyQt5.QtSerialPort import QSerialPortInfo, QSerialPort
from QCandyUi import CandyWindow

import re
import knn
import numpy as np

# Define expected header for continuous CSV saving
EXPECTED_SPECTRUM_KEYS = sorted(['R', 'S', 'T', 'U', 'V', 'W'])

class SerialAssistant(QMainWindow):
    EXPECTED_SPECTRUM_KEYS = EXPECTED_SPECTRUM_KEYS # Make it a class attribute for easy access

    def __init__(self):
        super().__init__()
        self.setWindowTitle("塑料识别系统")
        self.setGeometry(100, 100, 600, 500) # Increased height for new controls

        self.serial_port = QSerialPort(self)
        self.spectrum_data = {} # 用于存储光谱数据
        self.accumulated_spectrum_points = [] 

        # Variables for saving logic
        self.continuous_save_filepath = None
        # self.is_continuous_saving = False # No longer needed, mode is from combo box

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        settings_layout = QGridLayout()
        self.port_label = QLabel("串口:")
        self.port_combo = QComboBox()
        self.refresh_ports()
        settings_layout.addWidget(self.port_label, 0, 0)
        settings_layout.addWidget(self.port_combo, 0, 1)

        self.baud_label = QLabel("波特率:")
        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText("115200")
        settings_layout.addWidget(self.baud_label, 0, 2)
        settings_layout.addWidget(self.baud_combo, 0, 3)

        self.data_bits_label = QLabel("数据位:")
        self.data_bits_combo = QComboBox()
        self.data_bits_combo.addItems(["5", "6", "7", "8"])
        self.data_bits_combo.setCurrentText("8")
        settings_layout.addWidget(self.data_bits_label, 1, 0)
        settings_layout.addWidget(self.data_bits_combo, 1, 1)

        self.parity_label = QLabel("校验位:")
        self.parity_combo = QComboBox()
        self.parity_combo.addItems(["无", "偶校验", "奇校验", "空校验", "标记校验"])
        self.parity_combo.setCurrentText("无")
        settings_layout.addWidget(self.parity_label, 1, 2)
        settings_layout.addWidget(self.parity_combo, 1, 3)

        self.stop_bits_label = QLabel("停止位:")
        self.stop_bits_combo = QComboBox()
        self.stop_bits_combo.addItems(["1", "1.5", "2"])
        self.stop_bits_combo.setCurrentText("1")
        settings_layout.addWidget(self.stop_bits_label, 2, 0)
        settings_layout.addWidget(self.stop_bits_combo, 2, 1)

        self.connect_button = QPushButton("打开串口")
        self.connect_button.clicked.connect(self.toggle_connection)
        settings_layout.addWidget(self.connect_button, 2, 3)
        
        self.refresh_button = QPushButton("刷新串口")
        self.refresh_button.clicked.connect(self.refresh_ports)
        settings_layout.addWidget(self.refresh_button, 0, 4)
        
        main_layout.addLayout(settings_layout)

        self.receive_text_edit = QTextEdit()
        self.receive_text_edit.setReadOnly(True)
        main_layout.addWidget(self.receive_text_edit)

        send_layout = QHBoxLayout()
        self.send_text_edit = QTextEdit()
        self.send_text_edit.setFixedHeight(50)
        send_layout.addWidget(self.send_text_edit)
        
        self.send_button = QPushButton("发送数据")
        self.send_button.clicked.connect(self.send_generic_data)
        self.send_button.setEnabled(False)
        send_layout.addWidget(self.send_button)

        self.identify_button = QPushButton("开始识别")
        self.identify_button.clicked.connect(self.start_identification)
        self.identify_button.setEnabled(False)
        send_layout.addWidget(self.identify_button)

        self.clear_button = QPushButton("清除显示")
        self.clear_button.clicked.connect(self.clear_display)
        send_layout.addWidget(self.clear_button)
        
        main_layout.addLayout(send_layout)

        # Result and Saving Layout
        result_save_layout = QGridLayout() # Using QGridLayout for better alignment

        self.result_label = QLabel("识别结果:")
        result_save_layout.addWidget(self.result_label, 0, 0)
        self.result_display = QLineEdit()
        self.result_display.setReadOnly(True)
        result_save_layout.addWidget(self.result_display, 0, 1, 1, 2) # Span 2 columns

        self.save_mode_label = QLabel("保存模式:")
        result_save_layout.addWidget(self.save_mode_label, 1, 0)
        self.save_mode_combo = QComboBox()
        self.save_mode_combo.addItems(["单次保存", "连续保存"])
        self.save_mode_combo.setEnabled(False)
        result_save_layout.addWidget(self.save_mode_combo, 1, 1)
        
        self.save_spectrum_button = QPushButton("保存光谱")
        self.save_spectrum_button.clicked.connect(self.execute_save_action)
        self.save_spectrum_button.setEnabled(False)
        result_save_layout.addWidget(self.save_spectrum_button, 1, 2)
        
        main_layout.addLayout(result_save_layout)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("未连接")

    def refresh_ports(self):
        self.port_combo.clear()
        ports = QSerialPortInfo.availablePorts()
        if not ports:
            self.port_combo.addItem("无可用串口")
        else:
            for port in ports:
                self.port_combo.addItem(port.portName(), port)

    def toggle_connection(self):
        if self.serial_port.isOpen():
            self.serial_port.close()
            self.connect_button.setText("打开串口")
            self.send_button.setEnabled(False)
            self.identify_button.setEnabled(False)
            self.set_controls_enabled(True) # Enables port/baud etc.
            self.status_bar.showMessage("串口已关闭")
            self.receive_text_edit.append("串口已关闭")
            
            self.save_mode_combo.setEnabled(False)
            self.save_spectrum_button.setEnabled(False)
            self.continuous_save_filepath = None # Reset continuous save path
            self.receive_text_edit.append("连续保存路径已重置 (如已设置)。")

        else:
            selected_port_info = self.port_combo.currentData()
            if not selected_port_info:
                 self.status_bar.showMessage("错误: 无选择串口或无可用串口")
                 self.receive_text_edit.append("错误: 无选择串口或无可用串口")
                 return

            self.serial_port.setPort(selected_port_info)
            self.serial_port.setBaudRate(int(self.baud_combo.currentText()))
            
            data_bits_map = {
                "5": QSerialPort.Data5, "6": QSerialPort.Data6,
                "7": QSerialPort.Data7, "8": QSerialPort.Data8
            }
            self.serial_port.setDataBits(data_bits_map[self.data_bits_combo.currentText()])

            parity_map = {
                "无": QSerialPort.NoParity, "偶校验": QSerialPort.EvenParity,
                "奇校验": QSerialPort.OddParity, "空校验": QSerialPort.SpaceParity,
                "标记校验": QSerialPort.MarkParity
            }
            self.serial_port.setParity(parity_map[self.parity_combo.currentText()])

            stop_bits_map = {
                "1": QSerialPort.OneStop, "1.5": QSerialPort.OneAndHalfStop, "2": QSerialPort.TwoStop
            }
            self.serial_port.setStopBits(stop_bits_map[self.stop_bits_combo.currentText()])

            if self.serial_port.open(QSerialPort.ReadWrite):
                self.connect_button.setText("关闭串口")
                self.send_button.setEnabled(True)
                self.identify_button.setEnabled(True)
                self.set_controls_enabled(False) # Disables port/baud etc.
                self.status_bar.showMessage(f"已连接到 {selected_port_info.portName()} @ {self.baud_combo.currentText()} bps")
                self.receive_text_edit.append(f"已连接到 {selected_port_info.portName()}")
                self.serial_port.readyRead.connect(self.receive_data)
                
                self.save_mode_combo.setEnabled(True)
                self.save_spectrum_button.setEnabled(True)
            else:
                self.status_bar.showMessage(f"打开串口失败: {self.serial_port.errorString()}")
                self.receive_text_edit.append(f"打开串口失败: {self.serial_port.errorString()}")
                self.save_mode_combo.setEnabled(False)
                self.save_spectrum_button.setEnabled(False)

    def set_controls_enabled(self, enabled):
        self.port_combo.setEnabled(enabled)
        self.baud_combo.setEnabled(enabled)
        self.data_bits_combo.setEnabled(enabled)
        self.parity_combo.setEnabled(enabled)
        self.stop_bits_combo.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)

    def receive_data(self):
        if not self.serial_port.isOpen():
            return
        
        received_byte_data = self.serial_port.readAll()
        if received_byte_data:
            decoded_data = received_byte_data.data().decode(errors='ignore')
            
            try:
                spectrum_match = re.search(r'([RSTUVW])\[(\d+\.\d+)]', decoded_data)
                if spectrum_match:
                    self.receive_text_edit.append(f"接收: {decoded_data.strip()}")
                    key = spectrum_match.group(1)
                    value = float(spectrum_match.group(2))
                    self.spectrum_data[key] = value
                    # Automatic saving on data reception is removed. User clicks button.
                
                current_batch_data_points_str = re.findall(r'\[(\d+\.\d+)]', decoded_data)
                if current_batch_data_points_str:
                    current_batch_float_points = [float(item) for item in current_batch_data_points_str]
                    if current_batch_float_points:
                        self.accumulated_spectrum_points.extend(current_batch_float_points)
                    
                    if len(self.accumulated_spectrum_points) >= 6:
                        points_for_prediction = self.accumulated_spectrum_points[:6]
                        self.predict_data(points_for_prediction)
            
            except ValueError as ve:
                self.receive_text_edit.append(f"数据转换错误: {ve}")
            except Exception as e:
                self.receive_text_edit.append(f"处理接收数据或识别时发生未知错误: {e}")

    def send_generic_data(self):
        if self.serial_port.isOpen():
            data_to_send_str = self.send_text_edit.toPlainText()
            if data_to_send_str:
                self.serial_port.write(data_to_send_str.encode())
                self.receive_text_edit.append(f"发送: {data_to_send_str}")
            else:
                self.status_bar.showMessage("发送内容不能为空")
        else:
            self.status_bar.showMessage("串口未打开")

    def start_identification(self):
        self.accumulated_spectrum_points = []
        self.result_display.clear()
        self.receive_text_edit.append("累积光谱点和识别结果已清零，开始新的识别周期。")
        self.status_bar.showMessage("开始新的识别周期")

        if self.serial_port.isOpen():
            command = "sc\r\n" 
            self.serial_port.write(command.encode('utf-8'))
            self.receive_text_edit.append(f"发送识别指令: {command.strip()}")
        else:
            self.status_bar.showMessage("串口未打开，无法开始识别")

    def execute_save_action(self):
        if not self.spectrum_data:
            self.status_bar.showMessage("没有光谱数据可供保存。")
            self.receive_text_edit.append("提示: 当前无光谱数据可供保存。")
            return

        current_mode = self.save_mode_combo.currentText()
        filepath = None

        if current_mode == "单次保存":
            default_filename = f"spectrum_data_single_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            filepath, _ = QFileDialog.getSaveFileName(
                self, 
                "保存单次光谱数据", 
                default_filename,
                "CSV文件 (*.csv);;所有文件 (*)"
            )
            if filepath:
                self._write_spectrum_to_file(filepath, is_single_save=True)
            else:
                self.status_bar.showMessage("单次保存已取消。")
                self.receive_text_edit.append("单次保存操作已取消或未选择文件。")
        
        elif current_mode == "连续保存":
            if self.continuous_save_filepath is None:
                default_filename = f"spectrum_data_continuous_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                filepath, _ = QFileDialog.getSaveFileName(
                    self, 
                    "选择连续保存路径", 
                    default_filename,
                    "CSV文件 (*.csv);;所有文件 (*)"
                )
                if filepath:
                    self.continuous_save_filepath = filepath
                    self.receive_text_edit.append(f"连续保存路径已设置为: {self.continuous_save_filepath}")
                    # Immediately save current data to initialize the file if needed
                    self._write_spectrum_to_file(self.continuous_save_filepath, is_single_save=False)
                else:
                    self.status_bar.showMessage("连续保存未启动 (未选择文件)。")
                    self.receive_text_edit.append("连续保存操作已取消或未选择文件路径。")
            else: # continuous_save_filepath is already set
                self._write_spectrum_to_file(self.continuous_save_filepath, is_single_save=False)
        
    def _write_spectrum_to_file(self, filepath, is_single_save):
        if not filepath: # Should ideally not happen if called from execute_save_action correctly
            self.receive_text_edit.append("错误: 保存文件路径无效。")
            return
        if not self.spectrum_data: # Double check, though execute_save_action checks this
            self.receive_text_edit.append("提示: 无光谱数据写入。")
            return

        file_mode = 'w' if is_single_save else 'a'
        write_header = False
        if is_single_save:
            write_header = True
        else: # Continuous save
            write_header = not os.path.exists(filepath) or (os.path.exists(filepath) and os.path.getsize(filepath) == 0)

        try:
            with open(filepath, file_mode, newline='') as csvfile:
                csv_writer = csv.writer(csvfile)
                
                if write_header:
                    csv_writer.writerow(self.EXPECTED_SPECTRUM_KEYS)
                    self.receive_text_edit.append(f"写入表头 {self.EXPECTED_SPECTRUM_KEYS} 到 {filepath}")

                current_row_values = [self.spectrum_data.get(key, "") for key in self.EXPECTED_SPECTRUM_KEYS]
                
                if any(val != "" for val in current_row_values):
                    csv_writer.writerow(current_row_values)
                    if is_single_save:
                        self.status_bar.showMessage(f"光谱数据已保存至: {filepath}")
                        self.receive_text_edit.append(f"光谱数据已保存至: {filepath}")
                    else:
                        self.status_bar.showMessage(f"光谱数据已追加至: {filepath}")
                        self.receive_text_edit.append(f"光谱数据已追加至: {filepath}")

                else:
                    self.receive_text_edit.append(f"提示: 当前光谱数据中无任何与表头匹配的有效值，未写入空行到 {filepath}。")
            
        except Exception as e:
            self.status_bar.showMessage(f"保存数据出错: {str(e)}")
            self.receive_text_edit.append(f"保存数据出错: {str(e)}")
            if not is_single_save and self.continuous_save_filepath == filepath: # Error during continuous save
                self.receive_text_edit.append(f"连续保存至 {self.continuous_save_filepath} 失败。下次保存时请重新选择文件路径。")
                self.continuous_save_filepath = None # Reset path to force re-selection

    def clear_display(self):
        self.receive_text_edit.clear()
        self.result_display.clear()
        self.spectrum_data.clear()
        # self.continuous_save_filepath is not reset here, user might want to continue saving to same file after clearing.
        self.status_bar.showMessage("显示已清除")

    def predict_data(self, data_points_float):
        if len(data_points_float) == 6:
            try:
                data_array = np.array([data_points_float]) 

                knn_model_instance = knn.KNN() 
                knn_model = knn_model_instance.load('knn.pkl') 

                if knn_model: 
                    prediction = knn_model.predict(data_array) 
                    if prediction is not None and len(prediction) > 0:
                        result = prediction[0]
                        self.result_display.setText(str(result))
                    else:
                        self.receive_text_edit.append("KNN预测返回空结果。")
                        self.result_display.setText("预测失败")
                else:
                    self.receive_text_edit.append("KNN模型加载失败，无法预测。")
                    self.result_display.setText("模型加载失败")

            except FileNotFoundError:
                self.receive_text_edit.append("KNN模型文件 (knn.pkl) 未找到。")
                self.result_display.setText("模型文件缺失")
            except AttributeError as ae:
                self.receive_text_edit.append(f"KNN模块或函数调用出错: {ae}. 请确保 knn.py 正确且 KNN 类有 load 和 predict 方法。")
                self.result_display.setText("KNN代码错误")
            except Exception as e:
                self.receive_text_edit.append(f"KNN预测时发生未知错误: {e}")
                self.result_display.setText("预测未知错误")

    def closeEvent(self, event):
        if self.serial_port.isOpen():
            self.serial_port.close()
            # self.continuous_save_filepath = None # Already handled in toggle_connection when port closes
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # window = SerialAssistant() # Original
    window = CandyWindow.createWindow(SerialAssistant(), theme='blue', title='塑料识别系统') # Using CandyWindow
    window.show()
    sys.exit(app.exec_())
