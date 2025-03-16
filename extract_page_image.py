#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
从PDF文件中提取特定页面并保存为图像
"""

import os
import sys
import argparse
from pdf2image import convert_from_path

def extract_page_as_image(pdf_path, page_num, output_path):
    """从PDF中提取特定页面并保存为图像
    
    Args:
        pdf_path: PDF文件路径
        page_num: 要提取的页码(从1开始计数)
        output_path: 输出图像路径
    """
    if not os.path.exists(pdf_path):
        print(f"错误：PDF文件未找到: {pdf_path}")
        return False
    
    try:
        print(f"正在从PDF '{pdf_path}' 提取第 {page_num} 页...")
        # 转换指定页面（页码需要-1，因为pdf2image是从0开始计数）
        images = convert_from_path(pdf_path, first_page=page_num, last_page=page_num)
        
        if not images:
            print(f"错误：无法从PDF提取第 {page_num} 页")
            return False
        
        # 保存提取的图像
        image = images[0]
        image.save(output_path)
        print(f"成功：页面已保存为 '{output_path}'")
        return True
    
    except Exception as e:
        print(f"错误：提取页面时出现异常：{str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description="从PDF文件提取特定页面并保存为图像")
    parser.add_argument("--pdf", required=True, help="PDF文件路径")
    parser.add_argument("--page", type=int, required=True, help="要提取的页码（从1开始计数）")
    parser.add_argument("--output", help="输出图像文件路径")
    
    args = parser.parse_args()
    
    # 如果未指定输出路径，则使用默认路径
    if not args.output:
        pdf_name = os.path.splitext(os.path.basename(args.pdf))[0]
        args.output = f"{pdf_name}_page_{args.page}.png"
    
    # 提取页面
    success = extract_page_as_image(args.pdf, args.page, args.output)
    
    if success:
        print(f"页面提取成功！现在可以使用以下命令测试Gemini模型：")
        print(f"python test_gemini_simple.py --image \"{args.output}\"")
    else:
        print("页面提取失败")

if __name__ == "__main__":
    main()
