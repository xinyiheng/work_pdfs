#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import pickle
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

# 进度文件路径
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'progress.pkl')

def load_progress():
    """加载处理进度数据"""
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'rb') as f:
                progress_data = pickle.load(f)
            logger.info(f"已加载处理进度数据，共有 {len(progress_data)} 个PDF文件的进度记录")
            return progress_data
        except Exception as e:
            logger.error(f"加载进度数据时出错: {str(e)}")
            return {}
    else:
        logger.info("未找到进度数据文件")
        return {}

def check_unprocessed_files():
    """检查未处理或部分处理的PDF文件"""
    # 加载进度数据
    processing_progress = load_progress()
    
    # 获取Files目录路径
    files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Files")
    if not os.path.exists(files_dir):
        logger.error(f"Files目录不存在: {files_dir}")
        return
    
    # 递归查找所有PDF文件
    pdf_files = []
    for root, dirs, files in os.walk(files_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    total_files = len(pdf_files)
    logger.info(f"找到 {total_files} 个PDF文件")
    
    # 统计已处理、部分处理和未处理的文件
    completed_files = []
    partially_processed_files = []
    unprocessed_files = []
    
    # 检查每个PDF文件的处理状态
    for pdf_file in pdf_files:
        pdf_path_key = os.path.abspath(pdf_file)
        pdf_progress = processing_progress.get(pdf_path_key, {})
        
        # 检查处理状态
        if pdf_path_key in processing_progress and pdf_progress.get('completed', False):
            completed_files.append(pdf_file)
        elif pdf_path_key in processing_progress and pdf_progress.get('last_page') is not None:
            # 文件已部分处理
            last_page = pdf_progress.get('last_page', 0)
            partially_processed_files.append((pdf_file, last_page))
        else:
            # 文件尚未处理
            unprocessed_files.append(pdf_file)
    
    # 打印统计信息
    logger.info(f"统计结果:")
    logger.info(f"- 已完全处理: {len(completed_files)} 个文件")
    logger.info(f"- 部分处理: {len(partially_processed_files)} 个文件")
    logger.info(f"- 未处理: {len(unprocessed_files)} 个文件")
    
    # 打印部分处理的文件详情
    if partially_processed_files:
        logger.info("\n部分处理的文件:")
        for pdf_file, last_page in partially_processed_files:
            logger.info(f"- {os.path.basename(pdf_file)} (已处理到第 {last_page+1} 页)")
    
    # 打印未处理的文件详情
    if unprocessed_files:
        logger.info("\n未处理的文件:")
        for pdf_file in unprocessed_files:
            logger.info(f"- {os.path.basename(pdf_file)}")
    
    return {
        'completed': completed_files,
        'partially_processed': partially_processed_files,
        'unprocessed': unprocessed_files
    }

if __name__ == "__main__":
    check_unprocessed_files()
