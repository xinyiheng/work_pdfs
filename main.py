import os
import sys
import logging
import json
import pickle
from pathlib import Path
from dotenv import load_dotenv
import time

from pdf_processor import PDFProcessor
from webhook_handler import FeishuWebhook
from file_watcher import FileWatcher

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('pdf_extraction.log')
    ]
)
logger = logging.getLogger(__name__)

# Constants
WEBHOOK_URL = os.getenv('FEISHU_WEBHOOK_URL')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Files')
PROGRESS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'progress.pkl')  # 进度文件路径

# 处理进度记录
processing_progress = {}

# Initialize components
pdf_processor = None
webhook_handler = None

def load_progress():
    """加载处理进度数据"""
    global processing_progress
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, 'rb') as f:
                processing_progress = pickle.load(f)
            logger.info(f"已加载处理进度数据，共有 {len(processing_progress)} 个PDF文件的进度记录")
        except Exception as e:
            logger.error(f"加载进度数据时出错: {str(e)}")
            processing_progress = {}
    else:
        processing_progress = {}
        logger.info("未找到进度数据文件，将创建新的进度记录")

def save_progress():
    """保存处理进度数据"""
    try:
        with open(PROGRESS_FILE, 'wb') as f:
            pickle.dump(processing_progress, f)
        logger.info(f"已保存处理进度数据，共 {len(processing_progress)} 个PDF文件的进度记录")
    except Exception as e:
        logger.error(f"保存进度数据时出错: {str(e)}")

def setup():
    """Set up the application components"""
    global pdf_processor, webhook_handler
    
    # 加载进度数据
    load_progress()
    
    # Initialize components
    pdf_processor = PDFProcessor(OPENROUTER_API_KEY)
    # 设置进度回调函数
    pdf_processor.update_progress_callback = update_pdf_progress
    webhook_handler = FeishuWebhook(WEBHOOK_URL, api_key=OPENROUTER_API_KEY)
    
    logger.info(f"Initialized PDF processor with OpenRouter API key: {OPENROUTER_API_KEY[:5]}...{OPENROUTER_API_KEY[-5:]}")
    logger.info("Application setup complete")

def update_pdf_progress(pdf_path, current_page):
    """更新PDF处理进度"""
    global processing_progress
    pdf_path_key = os.path.abspath(pdf_path)
    
    # 更新进度记录
    if pdf_path_key not in processing_progress:
        processing_progress[pdf_path_key] = {}
    
    processing_progress[pdf_path_key].update({
        'last_page': current_page,
        'timestamp': time.time(),
        'completed': False  # 正在处理中，尚未完成
    })
    
    # 每处理10页保存一次进度，防止频繁写入
    if current_page % 10 == 0:
        save_progress()

def process_pdf_file(pdf_path):
    """Process a single PDF file and send results to webhook"""
    try:
        # Extract the filename for logging
        filename = os.path.basename(pdf_path)
        
        # Process the PDF
        logger.info(f"Processing {filename}")
        results = pdf_processor.process_and_format(str(Path(pdf_path)))
        
        if results:
            # Save results to a JSON file
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'results')
            os.makedirs(output_dir, exist_ok=True)
            
            # Use Path to handle special characters in filenames
            base_filename = Path(filename).stem
            json_filename = os.path.join(output_dir, f"{base_filename}.json")
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Saved results to {json_filename}")
            
            # Send to Feishu webhook
            webhook_handler.send_data(results, filename)
            
            # Save translated data to separate JSON files (with English and Chinese field names)
            webhook_handler.save_translated_data(results, filename, use_chinese_fields=False)  # 英文字段名
            webhook_handler.save_translated_data(results, filename, use_chinese_fields=True)   # 中文字段名
        else:
            logger.warning(f"No valid book information found in {filename}")
            
    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {str(e)}")

def ensure_json_record(pdf_file_path, extracted_data):
    """
    确保为处理过的PDF文件生成JSON记录文件
    
    Args:
        pdf_file_path: 处理过的PDF文件路径
        extracted_data: 从PDF中提取的数据
    """
    if not extracted_data:
        logger.warning(f"没有从 {pdf_file_path} 提取到任何数据，不生成JSON记录")
        return
    
    try:
        # 获取基础文件名（不包含扩展名）
        base_filename = Path(os.path.basename(pdf_file_path)).stem
        
        # 确保results目录存在
        results_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
        if not os.path.exists(results_dir):
            os.makedirs(results_dir)
            logger.info(f"创建results目录: {results_dir}")
        
        # 保存原始英文数据
        original_json_path = os.path.join(results_dir, f"{base_filename}.json")
        with open(original_json_path, 'w', encoding='utf-8') as f:
            json.dump(extracted_data, f, ensure_ascii=False, indent=2)
        logger.info(f"保存原始数据到: {original_json_path}")
        
        # 创建翻译后的数据
        translated_data = []
        for book in extracted_data:
            title_value = book.get("title", "")
            author_value = book.get("Author", "")
            summary_value = book.get("Summary", "")
            publisher_value = book.get("Publisher", "")
            date_value = book.get("Date", "")
            theme_value = book.get("Theme", "")
            author_bio_value = book.get("Author_bio", "")
            
            # 使用FeishuWebhook的翻译方法进行翻译
            webhook = FeishuWebhook()
            title = webhook.translate_to_chinese(title_value, is_title=True)
            summary = webhook.translate_to_chinese(summary_value)
            date = webhook.translate_to_chinese(date_value)
            theme = webhook.translate_to_chinese(theme_value)
            author_bio = webhook.translate_to_chinese(author_bio_value)
            
            # 创建翻译后的书籍条目
            translated_book = {
                "title": title,
                "Author": author_value,  # 保持作者名称不变
                "Summary": summary,
                "Publisher": publisher_value,  # 保持出版商名称不变
                "Date": date,
                "Theme": theme,
                "Author_bio": author_bio,
                "original_title": title_value
            }
            
            translated_data.append(translated_book)
        
        # 保存翻译后的数据
        translated_json_path = os.path.join(results_dir, f"{base_filename}_translated.json")
        with open(translated_json_path, 'w', encoding='utf-8') as f:
            json.dump(translated_data, f, ensure_ascii=False, indent=2)
        logger.info(f"保存翻译后的数据到: {translated_json_path}")
        
        # 创建中文字段的翻译数据
        translated_cn_data = []
        for book in translated_data:
            cn_book = {
                "标题": book["title"],
                "作者": book["Author"],
                "摘要": book["Summary"],
                "出版社": book["Publisher"],
                "出版日期": book["Date"],
                "主题": book["Theme"],
                "作者简介": book["Author_bio"],
                "原始标题": book["original_title"]
            }
            translated_cn_data.append(cn_book)
        
        # 保存中文字段的翻译数据
        translated_cn_json_path = os.path.join(results_dir, f"{base_filename}_translated_cn_fields.json")
        with open(translated_cn_json_path, 'w', encoding='utf-8') as f:
            json.dump(translated_cn_data, f, ensure_ascii=False, indent=2)
        logger.info(f"保存中文字段翻译数据到: {translated_cn_json_path}")
        
        return True
    except Exception as e:
        logger.error(f"生成JSON记录时出错: {str(e)}")
        return False

def test_single_pdf():
    """Test function to process a single PDF file"""
    setup()
    
    # 获取全局参数
    global args
    
    # 检查是否指定了测试文件
    test_pdf_arg = args.test_pdf if hasattr(args, 'test_pdf') else None
    max_pages = args.max_pages if hasattr(args, 'max_pages') else None
    force_reprocess = args.force if hasattr(args, 'force') else False
    custom_start_page = args.start_page if hasattr(args, 'start_page') else None
    
    # 如果指定了测试文件，则使用指定的文件
    if test_pdf_arg:
        # 处理相对路径和绝对路径
        if os.path.isabs(test_pdf_arg) and os.path.exists(test_pdf_arg):
            test_pdf = test_pdf_arg
            logger.info(f"Using absolute path: {test_pdf}")
        else:
            # 尝试在Files目录中查找匹配的文件
            files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Files")
            logger.info(f"Searching for files in: {files_dir}")
            
            # 获取搜索模式
            search_pattern = os.path.basename(test_pdf_arg)
            logger.info(f"Original search pattern: {search_pattern}")
            
            # 列出Files目录中的所有文件
            try:
                all_files = os.listdir(files_dir)
                logger.info(f"Found {len(all_files)} files in directory")
                
                # 1. 首先尝试精确匹配（区分大小写）
                test_pdf = None
                for file in all_files:
                    if file == search_pattern:
                        test_pdf = os.path.join(files_dir, file)
                        logger.info(f"Found exact match: {test_pdf}")
                        break
                
                # 2. 如果没有找到精确匹配，尝试不区分大小写的完全匹配
                if not test_pdf:
                    for file in all_files:
                        if file.lower() == search_pattern.lower():
                            test_pdf = os.path.join(files_dir, file)
                            logger.info(f"Found case-insensitive match: {test_pdf}")
                            break
                
                # 3. 如果仍然没有找到，使用difflib找到最接近的匹配
                if not test_pdf:
                    import difflib
                    closest_matches = difflib.get_close_matches(search_pattern, 
                                                              [f for f in all_files if f.lower().endswith('.pdf')], 
                                                              n=1, cutoff=0.7)
                    if closest_matches:
                        test_pdf = os.path.join(files_dir, closest_matches[0])
                        logger.info(f"Found closest match: {test_pdf}")
                
                # 4. 如果还是没找到，尝试更宽松的匹配
                if not test_pdf:
                    # 移除扩展名，只保留文件名的主要部分
                    base_name = os.path.splitext(search_pattern)[0]
                    for file in all_files:
                        # 检查文件名是否包含搜索模式的主要部分（不区分大小写）
                        if base_name.lower() in os.path.splitext(file)[0].lower():
                            test_pdf = os.path.join(files_dir, file)
                            logger.info(f"Found partial match by base name: {test_pdf}")
                            break
                
                # 5. 最后，如果文件名中包含括号，尝试特殊处理
                if not test_pdf and '(' in search_pattern:
                    # 提取括号前的部分作为关键词
                    key_part = search_pattern.split('(')[0].strip()
                    # 提取括号内的部分作为次要关键词
                    bracket_part = search_pattern.split('(')[1].split(')')[0].strip() if ')' in search_pattern else ""
                    
                    logger.info(f"Trying to match with key part: '{key_part}' and bracket part: '{bracket_part}'")
                    
                    # 首先尝试同时匹配两个部分
                    for file in all_files:
                        if key_part.lower() in file.lower() and bracket_part.lower() in file.lower():
                            test_pdf = os.path.join(files_dir, file)
                            logger.info(f"Found match with both key parts: {test_pdf}")
                            break
                    
                    # 如果仍然没找到，只匹配主要部分
                    if not test_pdf and key_part:
                        exact_matches = []
                        for file in all_files:
                            if key_part.lower() == os.path.splitext(file)[0].lower():
                                exact_matches.append(file)
                            elif key_part.lower() in file.lower():
                                test_pdf = os.path.join(files_dir, file)
                                logger.info(f"Found match with main key part: {test_pdf}")
                                break
                        
                        # 如果找到多个精确匹配，优先选择包含括号内关键词的
                        if exact_matches and not test_pdf:
                            for match in exact_matches:
                                if bracket_part.lower() in match.lower():
                                    test_pdf = os.path.join(files_dir, match)
                                    logger.info(f"Found match from exact matches with bracket part: {test_pdf}")
                                    break
                            
                            # 如果仍然没找到，使用第一个精确匹配
                            if not test_pdf:
                                test_pdf = os.path.join(files_dir, exact_matches[0])
                                logger.info(f"Using first exact match: {test_pdf}")
                
                # 如果所有方法都失败，尝试直接使用原始路径
                if not test_pdf:
                    potential_path = os.path.join(files_dir, search_pattern)
                    logger.info(f"Trying direct path as last resort: {potential_path}")
                    if os.path.exists(potential_path):
                        test_pdf = potential_path
                        logger.info(f"Found file at direct path: {test_pdf}")
            except Exception as e:
                logger.error(f"Error during file search: {str(e)}")
    else:
        # 默认测试文件
        test_pdf = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Files", "LGR Spring 2025 Rights Guide.pdf")
    
    if test_pdf and os.path.exists(test_pdf):
        logger.info(f"Testing with file: {test_pdf}")
        try:
            # 检查是否已经处理过该文件
            pdf_path_key = os.path.abspath(test_pdf)
            
            # 如果强制重新处理，则移除之前的进度
            if force_reprocess and pdf_path_key in processing_progress:
                del processing_progress[pdf_path_key]
                logger.info(f"强制重新处理，已删除文件 {test_pdf} 的进度记录")
            
            # 查看处理进度
            pdf_progress = processing_progress.get(pdf_path_key, {})
            
            # 如果文件已完全处理且不强制重新处理，则跳过
            if pdf_progress.get('completed', False) and not force_reprocess:
                logger.info(f"文件 {test_pdf} 已完全处理，跳过")
                return
            
            # 提取书籍信息，支持从上次处理的页码继续
            start_page = pdf_progress.get('last_page', 0)  # 默认从第1页开始（索引为0）
            
            # 如果指定了自定义起始页，则使用自定义起始页
            if custom_start_page is not None and (force_reprocess or start_page <= 0):
                start_page = custom_start_page
                logger.info(f"使用自定义起始页: {start_page+1}")
            
            # 处理PDF并获取书籍数据
            book_data = pdf_processor.process_and_format(test_pdf, max_pages=max_pages, start_page=start_page)
            
            if book_data:
                # 确保生成JSON记录
                ensure_json_record(test_pdf, book_data)
                
                # 发送到飞书
                webhook_handler.send_data(book_data, test_pdf)
                # 保存翻译后的数据（使用中文字段名）
                webhook_handler.save_translated_data(book_data, test_pdf, use_chinese_fields=True)
                logger.info(f"Successfully processed {test_pdf}")
                
                # 标记该文件已完全处理
                processing_progress[pdf_path_key] = {
                    'completed': True,
                    'last_page': None,  # 完全处理后不需要记录页码
                    'timestamp': time.time()
                }
                save_progress()
            else:
                logger.warning(f"No book data extracted from {test_pdf}")
        except Exception as e:
            logger.error(f"Error processing {test_pdf}: {str(e)}")
    else:
        logger.error(f"Test file not found. Tried to use: {test_pdf_arg if test_pdf_arg else test_pdf}")
        # 列出Files目录中的所有文件，帮助用户找到正确的文件名
        files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Files")
        if os.path.exists(files_dir):
            try:
                all_files = os.listdir(files_dir)
                logger.info(f"Available files in {files_dir}:")
                for file in all_files:
                    if file.lower().endswith('.pdf'):
                        logger.info(f"  - {file}")
                
                # 如果用户指定了文件，尝试找到最接近的匹配
                if test_pdf_arg:
                    import difflib
                    search_name = os.path.basename(test_pdf_arg)
                    closest_matches = difflib.get_close_matches(search_name, 
                                                              [f for f in all_files if f.lower().endswith('.pdf')], 
                                                              n=3, cutoff=0.3)
                    if closest_matches:
                        logger.info("Did you mean one of these files?")
                        for match in closest_matches:
                            logger.info(f"  - {match}")
            except Exception as e:
                logger.error(f"Error listing directory: {str(e)}")

def process_all_pdfs():
    """Process all PDF files in the Files directory and its subdirectories"""
    setup()
    
    # 获取全局参数
    global args
    max_pages = args.max_pages if hasattr(args, 'max_pages') else None
    limit = args.limit if hasattr(args, 'limit') else 0
    force_reprocess = args.force if hasattr(args, 'force') else False
    custom_start_page = args.start_page if hasattr(args, 'start_page') else None
    
    # 获取Files目录路径
    files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Files")
    if not os.path.exists(files_dir):
        logger.error(f"Files目录不存在: {files_dir}")
        return
    
    logger.info(f"开始处理Files目录中的所有PDF文件: {files_dir}")
    
    # 递归查找所有PDF文件
    pdf_files = []
    for root, dirs, files in os.walk(files_dir):
        for file in files:
            if file.lower().endswith('.pdf'):
                pdf_files.append(os.path.join(root, file))
    
    total_files = len(pdf_files)
    logger.info(f"找到 {total_files} 个PDF文件")
    
    # 如果设置了限制，则只处理指定数量的文件
    if limit > 0 and limit < total_files:
        pdf_files = pdf_files[:limit]
        logger.info(f"根据限制，只处理前 {limit} 个文件")
    
    # 统计已处理、部分处理和未处理的文件数量
    completed_files = 0
    partially_processed_files = 0
    unprocessed_files = 0
    
    # 处理每个PDF文件
    for i, pdf_file in enumerate(pdf_files):
        pdf_path_key = os.path.abspath(pdf_file)
        pdf_progress = processing_progress.get(pdf_path_key, {})
        
        # 如果强制重新处理，则移除之前的进度
        if force_reprocess and pdf_path_key in processing_progress:
            del processing_progress[pdf_path_key]
            pdf_progress = {}
            logger.info(f"强制重新处理，已删除文件 {pdf_file} 的进度记录")
        
        # 如果文件已完全处理且不强制重新处理，则跳过
        if pdf_progress.get('completed', False) and not force_reprocess:
            logger.info(f"文件 [{i+1}/{len(pdf_files)}] 已完全处理，跳过: {pdf_file}")
            completed_files += 1
            continue
        
        # 提取上次处理到的页码
        start_page = pdf_progress.get('last_page', 0)  # 默认从第1页开始（索引为0）
        
        # 如果指定了自定义起始页，则使用自定义起始页
        if custom_start_page is not None and (force_reprocess or start_page <= 0):
            start_page = custom_start_page
            logger.info(f"使用自定义起始页: {start_page+1}")
        
        # 如果不是从头开始，提示继续处理
        if start_page > 0 and not force_reprocess:
            logger.info(f"继续处理文件 [{i+1}/{len(pdf_files)}]，从页码 {start_page+1} 开始: {pdf_file}")
            partially_processed_files += 1
        else:
            logger.info(f"开始处理文件 [{i+1}/{len(pdf_files)}]: {pdf_file}")
            unprocessed_files += 1
        
        try:
            # 提取书籍信息
            book_data = pdf_processor.process_and_format(pdf_file, max_pages=max_pages, start_page=start_page)
            
            if book_data:
                # 确保生成JSON记录
                ensure_json_record(pdf_file, book_data)
                
                # 发送到飞书
                webhook_handler.send_data(book_data, pdf_file)
                # 保存翻译后的数据（使用中文字段名）
                webhook_handler.save_translated_data(book_data, pdf_file, use_chinese_fields=True)
                logger.info(f"成功处理文件 [{i+1}/{len(pdf_files)}]: {pdf_file}")
                
                # 标记该文件已完全处理
                processing_progress[pdf_path_key] = {
                    'completed': True,
                    'last_page': None,  # 完全处理后不需要记录页码
                    'timestamp': time.time()
                }
                save_progress()
            else:
                logger.warning(f"未从文件中提取到书籍数据 [{i+1}/{len(pdf_files)}]: {pdf_file}")
        except Exception as e:
            logger.error(f"处理文件时出错 [{i+1}/{len(pdf_files)}] {pdf_file}: {str(e)}")
            # 继续处理下一个文件
            continue
    
    logger.info(f"所有PDF文件处理完成，共处理 {len(pdf_files)} 个文件")
    logger.info(f"已完全处理: {completed_files} 个文件，部分处理: {partially_processed_files} 个文件，新处理: {unprocessed_files} 个文件")

def watch_files():
    """启动文件监视器，监视Files目录中的新PDF文件并处理它们"""
    setup()
    
    # 获取全局参数
    global args
    max_pages = args.max_pages if hasattr(args, 'max_pages') else None
    force_reprocess = args.force if hasattr(args, 'force') else False
    custom_start_page = args.start_page if hasattr(args, 'start_page') else None
    
    logger.info("启动文件监视器，监视Files目录中的新PDF文件")
    
    # 定义回调函数，用于处理新检测到的PDF文件
    def process_new_pdf(pdf_path):
        try:
            logger.info(f"检测到新的PDF文件: {pdf_path}")
            
            # 确保使用Path对象处理路径，避免特殊字符问题
            pdf_path = str(Path(pdf_path))
            
            # 检查是否已经处理过该文件
            pdf_path_key = os.path.abspath(pdf_path)
            pdf_progress = processing_progress.get(pdf_path_key, {})
            
            # 如果强制重新处理，则移除之前的进度
            if force_reprocess and pdf_path_key in processing_progress:
                del processing_progress[pdf_path_key]
                logger.info(f"强制重新处理，已删除文件 {pdf_path} 的进度记录")
            
            # 如果文件已完全处理且不强制重新处理，则跳过
            if pdf_progress.get('completed', False) and not force_reprocess:
                logger.info(f"文件 {pdf_path} 已完全处理，跳过")
                return
            
            # 提取上次处理到的页码
            start_page = pdf_progress.get('last_page', 0)  # 默认从第1页开始（索引为0）
            
            # 如果指定了自定义起始页，则使用自定义起始页
            if custom_start_page is not None and (force_reprocess or start_page <= 0):
                start_page = custom_start_page
                logger.info(f"使用自定义起始页: {start_page+1}")
            
            # 处理PDF并获取书籍数据
            book_data = pdf_processor.process_and_format(pdf_path, max_pages=max_pages, start_page=start_page)
            
            if book_data:
                # 确保生成JSON记录
                ensure_json_record(pdf_path, book_data)
                
                # 发送到飞书
                webhook_handler.send_data(book_data, pdf_path)
                # 保存翻译后的数据（使用中文字段名）
                webhook_handler.save_translated_data(book_data, pdf_path, use_chinese_fields=True)
                logger.info(f"成功处理文件: {pdf_path}")
                
                # 标记该文件已完全处理
                processing_progress[pdf_path_key] = {
                    'completed': True,
                    'last_page': None,  # 完全处理后不需要记录页码
                    'timestamp': time.time()
                }
                save_progress()
            else:
                logger.warning(f"未从文件中提取到书籍数据: {pdf_path}")
        except Exception as e:
            logger.error(f"处理文件时出错 {pdf_path}: {str(e)}")
    
    # 创建并启动文件监视器
    files_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Files")
    if not os.path.exists(files_dir):
        logger.error(f"Files目录不存在: {files_dir}")
        return
    
    watcher = FileWatcher(files_dir, process_new_pdf)
    
    # 处理目录中已存在的未处理文件
    logger.info("检查目录中已存在的未处理文件")
    watcher.process_existing_files(process_all=force_reprocess)
    
    # 启动监视器，等待新文件
    logger.info(f"开始监视目录: {files_dir}")
    watcher.start()

def main():
    """Main entry point"""
    # 解析命令行参数
    global args
    import argparse
    
    parser = argparse.ArgumentParser(description='PDF书籍信息提取工具')
    parser.add_argument('--watch', action='store_true', help='启动文件监视器')
    parser.add_argument('--test', action='store_true', help='运行单个PDF测试')
    parser.add_argument('--test-pdf', type=str, help='要处理的PDF文件路径')
    parser.add_argument('--process-all', action='store_true', help='处理Files目录中的所有PDF文件')
    parser.add_argument('--max-pages', type=int, default=None, help='要处理的最大页数，默认为None（处理整个PDF）')
    parser.add_argument('--limit', type=int, default=0, help='处理所有文件时的最大文件数限制，默认为0（处理所有文件）')
    parser.add_argument('--force', action='store_true', help='强制重新处理所有文件，忽略之前的处理进度')
    parser.add_argument('--start-page', type=int, default=None, help='开始处理的页码（从0开始计数），默认为0（即第1页）')
    args = parser.parse_args()
    
    # 设置日志
    logger.info("Starting PDF extraction application")
    
    if args.watch:
        # 启动文件监视器
        watch_files()
    elif args.test or args.test_pdf:
        # 运行单个PDF测试
        test_single_pdf()
    elif args.process_all:
        # 处理所有PDF文件
        process_all_pdfs()
    else:
        # 默认运行单个PDF测试
        test_single_pdf()

if __name__ == "__main__":
    main()
