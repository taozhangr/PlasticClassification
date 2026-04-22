import os
import glob
import pandas as pd
from datetime import datetime


def merge_csv_files():
    """
    合并data文件夹中所有的CSV文件为一个文件
    假设所有CSV文件具有相同的表头结构
    """
    # 获取当前目录
    open_fath = 'data/pe'
    save_path = 'train_data/pe.csv'

    current_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(current_dir, open_fath)
    
    # 检查data文件夹是否存在，如果不存在则创建
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"创建data文件夹: {data_dir}")
        print("请将CSV文件放入data文件夹后再运行此脚本")
        return

    # 获取data文件夹中所有CSV文件
    csv_files = glob.glob(os.path.join(data_dir, "*.csv"))
    
    if not csv_files:
        print("未在data文件夹中找到CSV文件")
        return
    
    print(f"找到{len(csv_files)}个CSV文件:")
    for file in csv_files:
        print(f"  - {os.path.basename(file)}")
    
    # 使用pandas读取和合并所有CSV文件
    all_data = []
    header = None
    
    for file in csv_files:
        try:
            # 读取CSV文件
            df = pd.read_csv(file, header=0)
            
            # 获取文件名作为标识符（不含扩展名）
            file_identifier = os.path.splitext(os.path.basename(file))[0]
            
            # 如果是第一个文件，保存表头
            if header is None:
                header = list(df.columns)
            
            # 检查表头是否一致
            if list(df.columns) != header:
                print(f"警告: 文件 {os.path.basename(file)} 的表头与其他文件不一致，将尝试调整")
                # 重新排列列以匹配第一个文件的表头
                df = df.reindex(columns=header)
            
            # 为每行添加文件标识符列
            df['文件名'] = file_identifier
            
            # 添加到数据列表
            all_data.append(df)
        except Exception as e:
            print(f"处理文件 {os.path.basename(file)} 时出错: {str(e)}")
    
    if not all_data:
        print("没有有效的数据可合并")
        return
    
    # 合并所有数据
    merged_data = pd.concat(all_data, ignore_index=True)
    
    # 创建输出文件名（使用当前时间）
    datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(current_dir, save_path)
    
    # 保存合并后的数据
    merged_data.to_csv(output_file, index=False, encoding='utf-8-sig')
    
    print(f"已成功合并{len(csv_files)}个CSV文件")
    print(f"合并文件已保存为: {output_file}")


def main():
    print("开始合并CSV文件...")
    merge_csv_files()
    print("操作完成。")


if __name__ == "__main__":
    main()
